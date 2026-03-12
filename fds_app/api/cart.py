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

def _get_price(item_doc, variation_id, is_service):
    if int(is_service) == 0:
        return item_doc.custom_fixed_price or 0
    else:
        for row in (item_doc.custom_slots_and_variations_table or []):
            if str(row.variation) == str(variation_id):
                return row.price
        return 0

def _build_cart_data(cart_doc, base_url):
    item_doc = frappe.get_doc("Item", cart_doc.service)

    variation_name_en = None
    variation_name_ar = None
    unit_name_en = None
    unit_name_ar = None

    if cart_doc.variation:
        variation_doc = frappe.get_doc("Variations", cart_doc.variation)
        variation_name_en = variation_doc.name_en
        variation_name_ar = variation_doc.name_ar
        if variation_doc.unit:
            unit_doc = frappe.get_doc("Units", variation_doc.unit)
            unit_name_en = unit_doc.name_en
            unit_name_ar = unit_doc.name_ar

    return {
        "id": int(cart_doc.name),
        "product_id": cart_doc.service,
        "product_name": item_doc.item_name,
        "product_name_ar": item_doc.custom_item_name_ar,
        "product_description": item_doc.description,
        "product_description_ar": item_doc.custom_description_ar,
        "product_image": base_url + item_doc.image if item_doc.image else None,
        "product_variation_id": int(cart_doc.variation) if cart_doc.variation and str(cart_doc.variation).isdigit() else cart_doc.variation,
        "product_variation_name_en": variation_name_en,
        "product_variation_name_ar": variation_name_ar,
        "unit_name": unit_name_en,
        "unit_name_ar": unit_name_ar,
        "price": cart_doc.price,
        "qty": cart_doc.qty,
        "max_purchase_qty": item_doc.custom_max_per_order,
        "time_from": str(cart_doc.time_from) if cart_doc.time_from else None,
        "time_to": str(cart_doc.time_to) if cart_doc.time_to else None,
        "is_service": 1 if cart_doc.is_service else 0,
        "created_at": str(cart_doc.creation),
        "updated_at": str(cart_doc.modified),
    }


@frappe.whitelist(allow_guest=True)
def add_to_cart(customer_id=None, service_id=None, variation_id=None, qty=None, time_from=None, time_to=None, is_service=0):
    try:
        if not customer_id or not service_id or not variation_id or not qty:
            frappe.response["status"] = False
            frappe.response["message"] = "customer_id, service_id, variation_id and qty are required"
            frappe.response["cart"] = None
            return

        is_service = int(is_service)

        existing_carts = frappe.get_all(
            "Carts",
            filters={"customer": customer_id},
            fields=["name", "is_service"]
        )

        if existing_carts:
            if is_service == 1:
                if any(c.is_service == 1 for c in existing_carts):
                    frappe.response["status"] = False
                    frappe.response["message"] = "You already have a service in your cart. Only one service is allowed at a time."
                    frappe.response["cart"] = None
                    return
            if is_service == 0:
                if any(c.is_service == 1 for c in existing_carts):
                    frappe.response["status"] = False
                    frappe.response["message"] = "Cannot add products while a service is in your cart."
                    frappe.response["cart"] = None
                    return

        item_doc = frappe.get_doc("Item", service_id)
        price = _get_price(item_doc, variation_id, is_service)

        cart = frappe.get_doc({
            "doctype": "Carts",
            "service": service_id,
            "customer": customer_id,
            "variation": variation_id,
            "qty": int(qty),
            "price": price,
            "time_from": time_from,
            "time_to": time_to,
            "is_service": is_service
        })
        cart.insert(ignore_permissions=True)
        frappe.db.commit()

        base_url = frappe.utils.get_url()
        cart_data = _build_cart_data(cart, base_url)

        frappe.response["status"] = True
        frappe.response["message"] = "Item added to cart successfully"
        frappe.response["cart"] = cart_data

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add To Cart Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["cart"] = None


@frappe.whitelist(allow_guest=True)
def update_cart(cart_id=None, service_id=None, variation_id=None, qty=None):
    try:
        if not cart_id or not qty:
            frappe.response["status"] = False
            frappe.response["message"] = "cart_id and qty are required"
            return

        if not frappe.db.exists("Carts", cart_id):
            frappe.response["status"] = False
            frappe.response["message"] = "Cart item not found"
            return

        cart_doc = frappe.get_doc("Carts", cart_id)

        price = cart_doc.price
        if service_id and variation_id:
            item_doc = frappe.get_doc("Item", service_id)
            price = _get_price(item_doc, variation_id, cart_doc.is_service)

        cart_doc.qty = int(qty)
        cart_doc.price = price
        if variation_id:
            cart_doc.variation = str(variation_id)
        cart_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Cart updated successfully"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Cart Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"


@frappe.whitelist(allow_guest=True)
def remove_from_cart(cart_id=None):
    try:
        if not cart_id:
            frappe.response["status"] = False
            frappe.response["message"] = "cart_id is required"
            frappe.response["cart"] = None
            return

        if not frappe.db.exists("Carts", cart_id):
            frappe.response["status"] = False
            frappe.response["message"] = "Cart item not found"
            frappe.response["cart"] = None
            return

        base_url = frappe.utils.get_url()
        cart_doc = frappe.get_doc("Carts", cart_id)
        cart_data = _build_cart_data(cart_doc, base_url)

        frappe.delete_doc("Carts", cart_id, ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Cart item removed successfully"
        frappe.response["cart"] = cart_data

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Remove From Cart Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["cart"] = None


@frappe.whitelist(allow_guest=True)
def get_cart_list(customer_id=None):
    try:
        if not customer_id:
            frappe.response["status"] = False
            frappe.response["message"] = "customer_id is required"
            frappe.response["data"] = []
            frappe.response["price"] = None
            return

        base_url = frappe.utils.get_url()

        carts = frappe.get_all(
            "Carts",
            filters={"customer": customer_id},
            fields=["name"],
            order_by="creation asc"
        )

        cart_list = []
        total_amount = 0

        for c in carts:
            cart_doc = frappe.get_doc("Carts", c.name)
            cart_data = _build_cart_data(cart_doc, base_url)
            total_amount += (cart_doc.price or 0) * (cart_doc.qty or 1)
            cart_list.append(cart_data)

        frappe.response["status"] = True
        frappe.response["message"] = "Cart list fetched successfully"
        frappe.response["data"] = cart_list
        frappe.response["price"] = {
            "total_amount": total_amount,
            "total_payable_amount": total_amount
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Cart List Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []
        frappe.response["price"] = None