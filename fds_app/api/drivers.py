import json
import base64
import os
from collections.abc import Iterable
from six import string_types
import frappe
from frappe.utils import flt
from frappe import _
from frappe.utils import get_files_path
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
def driver_login(email=None, password=None, device_token=None):
    try:
        if not email or not password:
            frappe.response["status"] = False
            frappe.response["message"] = "Email and password are required"
            frappe.response["data"] = {}
            return

        site_url = frappe.utils.get_url()

        login_manager = LoginManager()
        login_manager.authenticate(user=email, pwd=password)
        login_manager.post_login()

        user = frappe.get_doc("User", email)

        driver = frappe.db.get_value("Drivers", {"user": email}, ["name", "driver_name", "device_token"], as_dict=True)
        if not driver:
            frappe.response["status"] = False
            frappe.response["message"] = "No driver record linked to this user"
            frappe.response["data"] = {}
            return

        if device_token:
            frappe.db.set_value("Drivers", driver.name, "device_token", device_token)
            frappe.db.commit()

        data = {
            "id": driver.name,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "mobile": user.mobile_no or "",
            "email": user.name or "",
            "device_token": device_token or driver.device_token or "",
            "gender": user.gender or "",
            "profile_image":  f"{site_url}{user.user_image}" if user.user_image else "",
            "login_type": "driver"
        }

        frappe.response["status"] = True
        frappe.response["message"] = "Login successful"
        frappe.response["data"] = data

    except frappe.exceptions.AuthenticationError:
        frappe.response["status"] = False
        frappe.response["message"] = "Invalid email or password"
        frappe.response["data"] = {}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Driver Login Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = {}

@frappe.whitelist(allow_guest=True)
def get_driver(id=None):
    try:
        if not id:
            frappe.response["status"] = False
            frappe.response["message"] = "Driver ID is required"
            frappe.response["data"] = {}
            return

        site_url = frappe.utils.get_url()
        
        driver = frappe.get_doc("Drivers", id)

        if not driver.user:
            frappe.response["status"] = False
            frappe.response["message"] = "This driver is not linked to any user"
            frappe.response["data"] = {}
            return

        user = frappe.get_doc("User", driver.user)

        data = {
            "id": driver.name,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "mobile": user.mobile_no or "",
            "email": user.name or "",
            "device_token": driver.device_token or "",
            "gender": user.gender or "",
            "profile_image": f"{site_url}{user.user_image}" if user.user_image else "",
            "login_type": "driver",
        }

        frappe.response["status"] = True
        frappe.response["message"] = "Driver details fetched successfully"
        frappe.response["data"] = data

    except frappe.DoesNotExistError:
        frappe.response["status"] = False
        frappe.response["message"] = "Driver not found"
        frappe.response["data"] = {}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_driver API Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = {}

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


def _get_driver_from_user(user_id):
    driver_name = frappe.db.get_value("Drivers", {"user": user_id}, "name")
    if not driver_name:
        return None
    return driver_name


def _build_order_response(order_doc, base_url):
    address_line = ""
    state_name = ""
    region_name = ""
    lat_lng = ""

    if order_doc.address:
        address_doc = frappe.get_doc("Customer Address", order_doc.address)
        address_line = address_doc.address or ""
        lat_lng = address_doc.lat_lng or ""
        if address_doc.state:
            state_name = frappe.db.get_value("State", address_doc.state, "name_en") or ""
        if address_doc.region:
            region_name = frappe.db.get_value("Region", address_doc.region, "name_en") or ""

    driver_name = ""
    driver_contact = ""
    if order_doc.driver:
        driver_doc = frappe.get_doc("Drivers", order_doc.driver)
        driver_name = driver_doc.driver_name or ""
        if driver_doc.user:
            driver_contact = frappe.db.get_value("User", driver_doc.user, "mobile_no") or ""

    product_details = []

    if order_doc.service_order:
        service_name = ""
        service_name_ar = ""
        service_image = ""
        variation_id = ""
        variation_name_en = ""
        variation_name_ar = ""

        if order_doc.service:
            item_doc = frappe.get_doc("Item", order_doc.service)
            service_name = item_doc.item_name or ""
            service_name_ar = item_doc.custom_item_name_ar or ""
            service_image = base_url + item_doc.image if item_doc.image else ""

        if order_doc.variation:
            variation_doc = frappe.get_doc("Variations", order_doc.variation)
            variation_id = variation_doc.name or ""
            variation_name_en = variation_doc.name_en or ""
            variation_name_ar = variation_doc.name_ar or ""

        product_details.append({
            "product_id": order_doc.service or "",
            "product_name": service_name,
            "product_name_ar": service_name_ar,
            "product_image": service_image,
            "qty": 1,
            "price": order_doc.total_price or 0,
            "amount": order_doc.total_price or 0,
            "variation_id": variation_id,
            "variation_name_en": variation_name_en,
            "variation_name_ar": variation_name_ar,
            "time_slot": order_doc.data_lnrd or "",
            "product_review": _get_customer_review(order_doc.customer, order_doc.service) if order_doc.service else None,
        })
    else:
        for row in (order_doc.services or []):
            item_doc = frappe.get_doc("Item", row.item_code)
            product_details.append({
                "product_id": row.item_code or "",
                "product_name": row.item_name or "",
                "product_name_ar": item_doc.custom_item_name_ar or "",
                "product_image": base_url + item_doc.image if item_doc.image else "",
                "qty": row.qty or 0,
                "price": row.rate or 0,
                "amount": row.amount or 0,
                "variation_id": "",
                "variation_name_en": "",
                "variation_name_ar": "",
                "time_slot": "",
                "product_review": _get_customer_review(order_doc.customer, row.item_code),
            })

    return {
        "id": int(order_doc.name),
        "status": order_doc.status or "",
        "payment_status": order_doc.payment_status or "",
        "payment_method": order_doc.payment_method or "",
        "total_price": order_doc.total_price or 0,
        "is_service_order": 1 if order_doc.service_order else 0,
        "order_date": str(order_doc.order_date) if order_doc.order_date else "",
        "note": order_doc.note or "",
        "driver_note": order_doc.driver_note or "",
        "time_slot": order_doc.data_lnrd or "",
        "created_at": str(order_doc.creation),
        "phone_no": order_doc.phone_number or "",
        "customer_name": order_doc.customer_first_name + " " + order_doc.customer_last_name,
        "email": order_doc.email or "",
        "address_line_1": address_line,
        "state": state_name,
        "region": region_name,
        "lat_lng": lat_lng,
        "driver_name": driver_name,
        "driver_contact": driver_contact,
        "product_details": product_details,
    }


def _get_status_filter(status):
    if not status:
        return None
    status_list = [s.strip() for s in status.split(",")]
    return ["in", status_list] if len(status_list) > 1 else status_list[0]

@frappe.whitelist(allow_guest=True)
def get_orders(user_id=None, status=None):
    try:
        if not user_id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id is required"
            frappe.response["data"] = []
            return

        driver_name = _get_driver_from_user(user_id)
        if not driver_name:
            frappe.response["status"] = False
            frappe.response["message"] = "Driver not found for this user"
            frappe.response["data"] = []
            return

        filters = {"driver": driver_name}
        status_filter = _get_status_filter(status)
        if status_filter:
            filters["status"] = status_filter

        orders = frappe.get_all(
            "Order",
            filters=filters,
            fields=["name"],
            order_by="creation desc"
        )

        base_url = frappe.utils.get_url()

        frappe.response["status"] = True
        frappe.response["message"] = "Orders fetched successfully"
        frappe.response["data"] = [
            _build_order_response(frappe.get_doc("Order", o.name), base_url)
            for o in orders
        ]

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Driver Get Orders Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []


@frappe.whitelist(allow_guest=True)
def get_order_detail(user_id=None, order_id=None):
    try:
        if not user_id or not order_id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id and order_id are required"
            frappe.response["data"] = None
            return

        driver_name = _get_driver_from_user(user_id)
        if not driver_name:
            frappe.response["status"] = False
            frappe.response["message"] = "Driver not found"
            frappe.response["data"] = None
            return

        if not frappe.db.exists("Order", order_id):
            frappe.response["status"] = False
            frappe.response["message"] = "Order not found"
            frappe.response["data"] = None
            return

        order_doc = frappe.get_doc("Order", order_id)

        if str(order_doc.driver) != str(driver_name):
            frappe.response["status"] = False
            frappe.response["message"] = "This order is not assigned to you"
            frappe.response["data"] = None
            return

        frappe.response["status"] = True
        frappe.response["message"] = "Order fetched successfully"
        frappe.response["data"] = _build_order_response(order_doc, frappe.utils.get_url())

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Driver Get Order Detail Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_order_status(user_id=None, id=None, status=None, driver_note=None):
    try:
        if not user_id or not id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id and id are required"
            return

        driver_name = _get_driver_from_user(user_id)
        if not driver_name:
            frappe.response["status"] = False
            frappe.response["message"] = "Driver not found"
            return

        if not frappe.db.exists("Order", id):
            frappe.response["status"] = False
            frappe.response["message"] = "Order not found"
            return

        order_doc = frappe.get_doc("Order", id)

        if str(order_doc.driver) != str(driver_name):
            frappe.response["status"] = False
            frappe.response["message"] = "This order is not assigned to you"
            return

        if status:
            order_doc.status = status
        if driver_note:
            order_doc.driver_note = driver_note

        order_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Order updated successfully"
        frappe.response["data"] = _build_order_response(order_doc, frappe.utils.get_url())

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Driver Update Order Status Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_order_payment(user_id=None, id=None, payment_status=None, payment_method=None):
    try:
        if not user_id or not id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id and id are required"
            return

        driver_name = _get_driver_from_user(user_id)
        if not driver_name:
            frappe.response["status"] = False
            frappe.response["message"] = "Driver not found"
            return

        if not frappe.db.exists("Order", id):
            frappe.response["status"] = False
            frappe.response["message"] = "Order not found"
            return

        order_doc = frappe.get_doc("Order", id)

        if str(order_doc.driver) != str(driver_name):
            frappe.response["status"] = False
            frappe.response["message"] = "This order is not assigned to you"
            return

        if payment_status:
            order_doc.payment_status = payment_status
        if payment_method:
            order_doc.payment_method = payment_method

        order_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Payment updated successfully"
        frappe.response["data"] = _build_order_response(order_doc, frappe.utils.get_url())

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Driver Update Order Payment Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None