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
def get_items(category_id=None, user_id=None, search=None):
    try:
        item_group = category_id

        base_url = frappe.utils.get_url()

        filters = {
            "item_group": item_group,
            "disabled": 0,
        }

        if search:
            filters["item_name"] = ["like", f"%{search}%"]

        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=[
                "name", "item_name", "custom_item_name_ar",
                "description", "custom_description_ar",
                "brand", "custom_max_per_order", "is_stock_item",
                "item_group", "image", "custom_holiday_list"
            ],
        )

        item_list = []

        for item in items:
            brand_name = None
            if item.brand:
                brand_name = frappe.db.get_value("Brand", item.brand, "brand")

            holiday_dates = []
            if item.custom_holiday_list:
                holiday_doc = frappe.get_doc("Holiday List", item.custom_holiday_list)
                if hasattr(holiday_doc, "holidays") and holiday_doc.holidays:
                    holiday_dates = [str(h.holiday_date) for h in holiday_doc.holidays]

            reviews_raw = frappe.get_all(
                "Reviews",
                filters={"service": item.name},
                fields=["name", "customer", "stars", "review"],
                order_by="creation desc"
            )

            review_list = []
            for r in reviews_raw:
                likes_count = frappe.db.count("Customers Table", {
                    "parent": r.name, "parenttype": "Reviews", "parentfield": "liked_by"
                })
                dislikes_count = frappe.db.count("Customers Table", {
                    "parent": r.name, "parenttype": "Reviews", "parentfield": "disliked_by"
                })

                is_user_like = 0
                is_user_dislike = 0

                if user_id:
                    is_user_like = 1 if frappe.db.exists("Customers Table", {
                        "parent": r.name, "parenttype": "Reviews",
                        "parentfield": "liked_by", "customer": user_id
                    }) else 0
                    is_user_dislike = 1 if frappe.db.exists("Customers Table", {
                        "parent": r.name, "parenttype": "Reviews",
                        "parentfield": "disliked_by", "customer": user_id
                    }) else 0

                review_list.append({
                    "id": int(r.name),
                    "product_id": item.name,
                    "user_id": r.customer,
                    "rating": r.stars,
                    "review_likes": likes_count,
                    "review_dislikes": dislikes_count,
                    "is_user_like": is_user_like,
                    "is_user_dislike": is_user_dislike,
                    "review_msg": r.review,
                    "user_name": frappe.get_value("Customer", r.customer, "customer_name")
                })

            reviews = frappe.get_all("Reviews", filters={"service": item.name}, fields=["stars"])
            rating_count = len(reviews)
            rating = round(sum([r.stars for r in reviews]) / rating_count, 1) if rating_count > 0 else 0

            is_wish_list = 0
            if user_id:
                is_wish_list = 1 if frappe.db.exists("Item Table", {
                    "parent": user_id,
                    "parenttype": "Customer",
                    "parentfield": "custom_wishlist_items",
                    "item": item.name
                }) else 0

            variation_data = []
            prices = []
            unit_name_en = None
            unit_name_ar = None
            item_doc = frappe.get_doc("Item", item.name)

            for row in (item_doc.custom_slots_and_variations_table or []):
                variation_doc = frappe.get_doc("Variations", row.variation)
                unit_doc = frappe.get_doc("Units", variation_doc.unit)
                variation_data.append({
                    "variation_id": variation_doc.name,
                    "variation_name_en": variation_doc.name_en,
                    "variation_name_ar": variation_doc.name_ar,
                    "from_time": row.get("from"),
                    "to_time": row.to,
                    "max_per_day": row.max_per_day,
                    "price": row.price
                })
                prices.append(row.price)
                if not unit_name_en:
                    unit_name_en = unit_doc.name_en
                    unit_name_ar = unit_doc.name_ar
            
            item_list.append({
                "id": item.name,
                "name_en": item.item_name,
                "name_ar": item.custom_item_name_ar,
                "desc_en": item.description,
                "desc_ar": item.custom_description_ar,
                "brand_name": brand_name,
                "is_service": item.is_stock_item == 0,
                "has_variation": item.is_stock_item == 0,
                "category": item.item_group,
                "image": base_url + item.image if item.image else None,
                "max_purchase_qty": item.custom_max_per_order,
                "holidays": holiday_dates,
                "reviews": review_list,
                "rating": rating,
                "rating_count": rating_count,
                "is_wish_list": is_wish_list,
                "min_price": min(prices) if prices else 0,
                "max_price": max(prices) if prices else 0,
                "unit_name": unit_name_en,
                "unit_name_ar": unit_name_ar,
                "variation_data": variation_data,
            })

        frappe.response["status"] = True
        frappe.response["message"] = "Items fetched successfully"
        frappe.response["data"] = item_list

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Items By Group Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def add_to_wishlist(user_id=None, item_id=None):
    try:
        if not user_id or not item_id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id and item_id are required"
            return

        # Check if already in wishlist
        already_exists = frappe.db.exists("Item Table", {
            "parent": user_id,
            "parenttype": "Customer",
            "parentfield": "custom_wishlist_items",
            "item": item_id
        })

        if already_exists:
            frappe.response["status"] = False
            frappe.response["message"] = "Item already in wishlist"
            return

        customer_doc = frappe.get_doc("Customer", user_id)
        customer_doc.append("custom_wishlist_items", {"item": item_id})
        customer_doc.save(ignore_permissions=True)

        frappe.response["status"] = True
        frappe.response["message"] = "Item added to wishlist"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add To Wishlist Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"


@frappe.whitelist(allow_guest=True)
def remove_from_wishlist(user_id=None, item_id=None):
    try:
        if not user_id or not item_id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id and item_id are required"
            return

        customer_doc = frappe.get_doc("Customer", user_id)

        # Filter out the item from wishlist
        customer_doc.custom_wishlist_items = [
            row for row in customer_doc.custom_wishlist_items
            if row.item != item_id
        ]
        customer_doc.save(ignore_permissions=True)

        frappe.response["status"] = True
        frappe.response["message"] = "Item removed from wishlist"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Remove From Wishlist Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"


@frappe.whitelist(allow_guest=True)
def get_wishlist(user_id=None):
    try:
        if not user_id:
            frappe.response["status"] = False
            frappe.response["message"] = "user_id is required"
            frappe.response["data"] = []
            return

        base_url = frappe.utils.get_url()

        wishlist_items = frappe.get_all(
            "Item Table",
            filters={
                "parent": user_id,
                "parenttype": "Customer",
                "parentfield": "custom_wishlist_items"
            },
            fields=["item"]
        )

        item_list = []

        for wish in wishlist_items:
            item = frappe.get_doc("Item", wish.item)

            # Reviews
            reviews = frappe.get_all(
                "Reviews",
                filters={"service": item.name},
                fields=["stars"]
            )
            rating_count = len(reviews)
            rating = round(sum([r.stars for r in reviews]) / rating_count, 1) if rating_count > 0 else 0

            # Variations & prices
            variation_data = []
            prices = []
            unit_name_en = None
            unit_name_ar = None

            for row in (item.custom_slots_and_variations_table or []):
                variation_doc = frappe.get_doc("Variations", row.variation)
                unit_doc = frappe.get_doc("Units", variation_doc.unit)
                variation_data.append({
                    "variation_id": variation_doc.name,
                    "variation_name_en": variation_doc.name_en,
                    "variation_name_ar": variation_doc.name_ar,
                    "from_time": row.get("from"),
                    "to_time": row.to,
                    "max_per_day": row.max_per_day,
                    "price": row.price
                })
                prices.append(row.price)
                if not unit_name_en:
                    unit_name_en = unit_doc.name_en
                    unit_name_ar = unit_doc.name_ar

            # Holiday dates
            holiday_dates = []
            if item.custom_holiday_list:
                holiday_doc = frappe.get_doc("Holiday List", item.custom_holiday_list)
                if hasattr(holiday_doc, "holidays") and holiday_doc.holidays:
                    holiday_dates = [str(h.holiday_date) for h in holiday_doc.holidays]

            item_list.append({
                "id": item.name,
                "name_en": item.item_name,
                "name_ar": item.custom_item_name_ar,
                "desc_en": item.description,
                "desc_ar": item.custom_description_ar,
                "is_service": item.is_stock_item == 0,
                "has_variation": item.is_stock_item == 0,
                "category": item.item_group,
                "image": base_url + item.image if item.image else None,
                "max_purchase_qty": item.custom_max_per_order,
                "holidays": holiday_dates,
                "rating": rating,
                "rating_count": rating_count,
                "min_price": min(prices) if prices else 0,
                "max_price": max(prices) if prices else 0,
                "unit_name": unit_name_en,
                "unit_name_ar": unit_name_ar,
                "variation_data": variation_data,
                "is_wish_list": 1  # always 1 since these are wishlist items
            })

        frappe.response["status"] = True
        frappe.response["message"] = "Wishlist fetched successfully"
        frappe.response["data"] = item_list

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Wishlist Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []
