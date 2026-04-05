import json
import base64
import os
from collections.abc import Iterable
from six import string_types
import frappe
from frappe.utils import flt
from frappe import _
from frappe.utils import get_files_path, cint
from frappe.utils.file_manager import save_file
from frappe.utils import nowdate, nowtime, get_first_day, getdate
from frappe.auth import LoginManager

def log_error(title, error):
    frappe.log_error(frappe.get_traceback(), title)

def flatten(lis):
    for item in lis:
        if isinstance(item, Iterable) and not isinstance(item, str):
            for x in flatten(item):
                yield x
        else:        
            yield item

@frappe.whitelist(allow_guest=True)
def get_free_slots(product_id=None, receive_date=None, variation_id=None):
    try:
        if not product_id or not receive_date or not variation_id:
            frappe.response["status"] = False
            frappe.response["message"] = "product_id, receive_date and variation_id are required"
            frappe.response["available_slots"] = []
            return

        item_doc = frappe.get_doc("Item", product_id)

        if item_doc.custom_holiday_list:
            holiday_doc = frappe.get_doc("Holiday List", item_doc.custom_holiday_list)
            holiday_dates = [str(h.holiday_date) for h in (holiday_doc.holidays or [])]
            if receive_date in holiday_dates:
                frappe.response["status"] = False
                frappe.response["message"] = "Selected date is a holiday, no slots available"
                frappe.response["available_slots"] = []
                return

        variation_rows = [
            row for row in (item_doc.custom_slots_and_variations_table or [])
            if str(row.variation) == str(variation_id)
        ]

        if not variation_rows:
            frappe.response["status"] = False
            frappe.response["message"] = "No slots found for this variation"
            frappe.response["available_slots"] = []
            return

        available_slots = []

        for row in variation_rows:
            max_per_day = row.max_per_day or 0
            time_from = str(row.get("from")) if row.get("from") is not None else None
            time_to = str(row.to) if row.to is not None else None

            booked_count = frappe.db.count("Order", {
                "service": product_id,
                "variation": variation_id,
                "data_lnrd": f"{time_from} - {time_to}",
                "order_date": receive_date,
                "status": ["not in", ["cancelled"]]
            })

            remaining = max_per_day - booked_count

            if remaining > 0:
                available_slots.append({
                    "count": remaining,
                    "time_from": time_from,
                    "time_to": time_to,
                })

        frappe.response["status"] = True
        frappe.response["message"] = "Free slots fetched successfully"
        frappe.response["available_slots"] = available_slots

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Free Slots Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["available_slots"] = []


def _find_driver_for_state(service_id, state):
    item_doc = frappe.get_doc("Item", service_id)
    for driver_row in (item_doc.custom_drivers or []):
        driver_doc = frappe.get_doc("Drivers", driver_row.driver)
        if driver_doc.disable:
            continue
        driver_states = [str(s.state) for s in (driver_doc.states or [])]
        if str(state) in driver_states:
            return driver_doc.name
    return None


def _build_order_data(order_doc):
    return {
        "order_id": int(order_doc.name),
        "total_price": order_doc.total_price,
        "status": order_doc.status,
        "payment_status": order_doc.payment_status,
        "payment_method": order_doc.payment_method,
        "payment_ref": order_doc.payment_ref,
        "is_service_order": 1 if order_doc.service_order else 0,
        "order_date": str(order_doc.order_date) if order_doc.order_date else None,
        "note": order_doc.note,
        "driver": order_doc.driver,
        "service": order_doc.service,
        "variation": order_doc.variation,
        "time_slot": order_doc.data_lnrd,
        "customer": order_doc.customer,
        "address": order_doc.address,
        "phone_number": order_doc.phone_number,
        "email": order_doc.email,
        "created_at": str(order_doc.creation),
    }


@frappe.whitelist(allow_guest=True)
def create_order(
    customer_id=None,
    address_id=None,
    phone_number=None,
    email=None,
    note=None,
    payment_method=None,
    payment_status=None,
    payment_ref=None,
    order_date=None,
):
    try:
        if not customer_id or not address_id:
            frappe.response["status"] = False
            frappe.response["message"] = "customer_id and address_id are required"
            frappe.response["data"] = None
            return

        address_doc = frappe.get_doc("Customer Address", address_id)
        if not address_doc.state:
            frappe.response["status"] = False
            frappe.response["message"] = "Customer address has no state assigned"
            frappe.response["data"] = None
            return

        cart_items = frappe.get_all(
            "Carts",
            filters={"customer": customer_id},
            fields=["name", "service", "variation", "qty", "price", "time_from", "time_to", "is_service"]
        )

        if not cart_items:
            frappe.response["status"] = False
            frappe.response["message"] = "Cart is empty"
            frappe.response["data"] = None
            return

        is_service_order = any(c.is_service == 1 for c in cart_items)
        total_price = sum((c.price or 0) * (c.qty or 1) for c in cart_items)
        customer_state = address_doc.state

        primary_service_id = cart_items[0].service
        driver = _find_driver_for_state(primary_service_id, customer_state)

        if not driver:
            frappe.response["status"] = False
            frappe.response["message"] = "No available driver for your area"
            frappe.response["data"] = None
            return

        order_fields = {
            "doctype": "Order",
            "customer": customer_id,
            "address": address_id,
            "phone_number": phone_number,
            "email": email,
            "order_date": order_date,
            "total_price": total_price,
            "status": "confirmed",
            "payment_status": payment_status,
            "payment_method": payment_method,
            "payment_ref": payment_ref,
            "note": note,
            "driver": driver,
        }

        if is_service_order:
            cart = cart_items[0]
            order_fields.update({
                "service_order": 1,
                "variation": cart.variation,
                "data_lnrd": f"{str(cart.time_from)} - {str(cart.time_to)}" if cart.time_from and cart.time_to else None,
                "service": cart.service,
            })
        else:
            services_rows = [
                {
                    "doctype": "Sales Invoice Item",
                    "item_code": c.service,
                    "item_name": frappe.db.get_value("Item", c.service, "item_name"),
                    "qty": c.qty,
                    "rate": c.price,
                    "amount": (c.price or 0) * (c.qty or 1),
                    "uom": frappe.db.get_value("Item", c.service, "stock_uom") or "Nos",
                    "conversion_factor": 1,
                    "base_rate": c.price,
                    "base_amount": (c.price or 0) * (c.qty or 1),
                    "income_account": frappe.db.get_value(
                        "Company", frappe.defaults.get_global_default("company"), "default_income_account"
                    ) or "Sales - FDS",
                    "cost_center": frappe.db.get_value(
                        "Company", frappe.defaults.get_global_default("company"), "cost_center"
                    ) or "Main - FDS",
                }
                for c in cart_items
            ]
            order_fields.update({
                "service_order": 0,
                "services": services_rows,
            })

        order = frappe.get_doc(order_fields)
        order.insert(ignore_permissions=True)
        frappe.db.commit()

        for c in cart_items:
            frappe.delete_doc("Carts", c.name, ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Order created successfully"
        frappe.response["data"] = _build_order_data(order)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Order Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None

def _build_order_response(order_doc, base_url):
    address_line = None
    state_name = None
    region_name = None
    lat_lng = None

    if order_doc.address:
        address_doc = frappe.get_doc("Customer Address", order_doc.address)
        address_line = address_doc.address
        lat_lng = address_doc.lat_lng
        if address_doc.state:
            state_name = frappe.db.get_value("State", address_doc.state, "name_en")
        if address_doc.region:
            region_name = frappe.db.get_value("Region", address_doc.region, "name_en")

    driver_name = None
    driver_contact = None
    if order_doc.driver:
        driver_doc = frappe.get_doc("Drivers", order_doc.driver)
        driver_name = driver_doc.driver_name
        if driver_doc.user:
            driver_contact = frappe.db.get_value("User", driver_doc.user, "mobile_no")

    customer_user = frappe.db.get_value("Customer", order_doc.customer, "custom_user")

    service_id = None
    service_name = None
    service_name_ar = None
    service_image = None
    variation_id = None
    variation_name_en = None
    variation_name_ar = None
    service_review = None
    product_details = []
    
    full_customer_name = order_doc.customer_first_name + " " + order_doc.customer_last_name

    if order_doc.service_order:
        if order_doc.service:
            item_doc = frappe.get_doc("Item", order_doc.service)
            service_id = item_doc.name
            service_name = item_doc.item_name
            service_name_ar = item_doc.custom_item_name_ar
            service_image = base_url + item_doc.image if item_doc.image else None
            service_review = _get_customer_review(order_doc.customer, order_doc.service)
            
        if order_doc.variation:
            variation_doc = frappe.get_doc("Variations", order_doc.variation)
            variation_id = variation_doc.name
            variation_name_en = variation_doc.name_en
            variation_name_ar = variation_doc.name_ar
    else:
        for row in (order_doc.services or []):
            item_doc = frappe.get_doc("Item", row.item_code)
            product_details.append({
                "product_id": row.item_code,
                "product_name": row.item_name,
                "product_name_ar": item_doc.custom_item_name_ar,
                "product_image": base_url + item_doc.image if item_doc.image else None,
                "qty": row.qty,
                "price": row.rate,
                "amount": row.amount,
                "product_review": _get_customer_review(order_doc.customer, row.item_code)
            })

    return {
        "id": int(order_doc.name),
        "status": order_doc.status,
        "payment_status": order_doc.payment_status,
        "payment_method": order_doc.payment_method,
        "total_price": order_doc.total_price,
        "is_service_order": 1 if order_doc.service_order else 0,
        "order_date": str(order_doc.order_date) if order_doc.order_date else None,
        "note": order_doc.note,
        "time_slot": order_doc.data_lnrd,
        "created_at": str(order_doc.creation),
        "customer_id": customer_user,
        "user_name": full_customer_name,
        "phone_no": order_doc.phone_number,
        "email": order_doc.email,
        "address_line_1": address_line,
        "state": state_name,
        "region": region_name,
        "lat_lng": lat_lng,
        "driver_name": driver_name,
        "driver_contact": driver_contact,
        "service_id": service_id,
        "service_name": service_name,
        "service_name_ar": service_name_ar,
        "service_image": service_image,
        "variation_id": variation_id,
        "variation_name_en": variation_name_en,
        "variation_name_ar": variation_name_ar,
        "service_review": service_review,
        "product_details": product_details,
    }


@frappe.whitelist(allow_guest=True)
def get_order_detail(order_id=None):
    try:
        if not order_id:
            frappe.response["status"] = False
            frappe.response["message"] = "order_id is required"
            frappe.response["data"] = None
            return

        if not frappe.db.exists("Order", order_id):
            frappe.response["status"] = False
            frappe.response["message"] = "Order not found"
            frappe.response["data"] = None
            return

        base_url = frappe.utils.get_url()
        order_doc = frappe.get_doc("Order", order_id)

        frappe.response["status"] = True
        frappe.response["message"] = "Order fetched successfully"
        frappe.response["data"] = _build_order_response(order_doc, base_url)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Order Detail Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None


@frappe.whitelist(allow_guest=True)
def get_order_list(customer_id=None, status=None):
    try:
        if not customer_id:
            frappe.response["status"] = False
            frappe.response["message"] = "customer_id is required"
            frappe.response["data"] = []
            return

        filters = {"customer": customer_id}
        if status:
            status_list = [s.strip() for s in status.split(",")]
            if len(status_list) > 1:
                filters["status"] = ["in", status_list]
            else:
                filters["status"] = status_list[0]

        orders = frappe.get_all(
            "Order",
            filters=filters,
            fields=["name"],
            order_by="creation desc"
        )

        base_url = frappe.utils.get_url()
        order_list = []

        for o in orders:
            order_doc = frappe.get_doc("Order", o.name)
            order_list.append(_build_order_response(order_doc, base_url))

        frappe.response["status"] = True
        frappe.response["message"] = "Orders fetched successfully"
        frappe.response["data"] = order_list

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Order List Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []


@frappe.whitelist(allow_guest=True)
def cancel_order(id=None):
    try:
        if not id:
            frappe.response["status"] = False
            frappe.response["message"] = "order id is required"
            return

        if not frappe.db.exists("Order", id):
            frappe.response["status"] = False
            frappe.response["message"] = "Order not found"
            return

        order_doc = frappe.get_doc("Order", id)

        if order_doc.status == "cancelled":
            frappe.response["status"] = False
            frappe.response["message"] = "Order is already cancelled"
            return

        if order_doc.status == "completed":
            frappe.response["status"] = False
            frappe.response["message"] = "Completed orders cannot be cancelled"
            return

        order_doc.status = "cancelled"
        order_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Order cancelled successfully"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Cancel Order Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"

def _get_customer_review(customer_id, product_id):
    review = frappe.db.get_value(
        "Reviews",
        {"service": product_id, "customer": customer_id},
        ["name", "stars", "review", "creation"],
        as_dict=True
    )

    if not review:
        return None

    likes_count = frappe.db.count("Customers Table", {
        "parent": review.name, "parenttype": "Reviews", "parentfield": "liked_by"
    })
    dislikes_count = frappe.db.count("Customers Table", {
        "parent": review.name, "parenttype": "Reviews", "parentfield": "disliked_by"
    })

    return {
        "id": int(review.name),
        "product_id": product_id,
        "user_id": customer_id,
        "rating": review.stars,
        "review_likes": likes_count,
        "review_dislikes": dislikes_count,
        "is_user_like": 0,
        "is_user_dislike": 0,
        "review_msg": review.review,
        "user_name": frappe.db.get_value("Customer", customer_id, "customer_name"),
        "created_at": str(review.creation)
    }