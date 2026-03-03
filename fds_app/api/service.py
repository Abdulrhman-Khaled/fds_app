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
def get_items_by_group(item_group, customer_id=None):
    try:
        if not item_group:
            frappe.response["status"] = False
            frappe.response["message"] = "Category is required"
            frappe.response["data"] = []
            return

        base_url = frappe.utils.get_url()
        
        items = frappe.get_all(
            "Item",
            filters={
                "item_group": item_group,
                "disabled": 0,
            },
            fields=[
                "name",
                "item_name",
                "custom_item_name_ar",
                "description",
                "custom_description_ar",
                "brand",
                "custom_max_per_order",
                "is_stock_item",
                "item_group",
                "image",
                "custom_holiday_list",
                "custom_slots_and_variations_table"
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
                    holiday_dates = [
                        h.holiday_date for h in holiday_doc.holidays
                    ]

            reviews_raw = frappe.get_all(
                "Reviews",
                filters={"service": item.name},
                fields=["name", "customer", "stars", "review"],
                order_by="creation desc"
            )

            review_list = []
            for r in reviews_raw:
                likes_count = frappe.db.count(
                    "Customers Table",
                    {
                        "parent": r.name,
                        "parenttype": "Reviews",
                        "parentfield": "liked_by"
                    }
                )

                dislikes_count = frappe.db.count(
                    "Customers Table",
                    {
                        "parent": r.name,
                        "parenttype": "Reviews",
                        "parentfield": "disliked_by"
                    }
                )

                is_user_like = 0
                is_user_dislike = 0

                if customer_id:
                    user_liked = frappe.db.exists(
                        "Customers Table",
                        {
                            "parent": r.name,
                            "parenttype": "Reviews",
                            "parentfield": "liked_by",
                            "customer": customer_id
                        }
                    )

                    user_disliked = frappe.db.exists(
                        "Customers Table",
                        {
                            "parent": r.name,
                            "parenttype": "Reviews",
                            "parentfield": "disliked_by",
                            "customer": customer_id
                        }
                    )

                    is_user_like = 1 if user_liked else 0
                    is_user_dislike = 1 if user_disliked else 0

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

            reviews = frappe.get_all(
                "Reviews",
                filters={"service": item.name},
                fields=["stars"]
            )

            rating_count = len(reviews)

            if rating_count > 0:
                total_stars = sum([r.stars for r in reviews])
                rating = round(total_stars / rating_count, 1)
            else:
                rating = 0

            variation_data = []
            prices = []
            unit_name_en = None
            unit_name_ar = None

            variation_rows = item.custom_slots_and_variations_table or []
            for row in variation_rows:
                variation_doc = frappe.get_doc("Variations", row.variation)
                unit_doc = frappe.get_doc("Units", variation_doc.unit)
                variation_data.append({
                    "variation_id": variation_doc.name,
                    "variation_name_en": variation_doc.name_en,
                    "variation_name_ar": variation_doc.name_ar,
                    "unit_name_en": unit_doc.name_en,
                    "unit_name_ar": unit_doc.name_ar,
                    "from_time": row.get("from"),
                    "to_time": row.to,
                    "max_per_day": row.max_per_day,
                    "price": row.price
                })
                prices.append(row.price)
                if not unit_name_en:
                    unit_name_en = unit_doc.name_en
                    unit_name_ar = unit_doc.name_ar

            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0

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
                "image":  base_url + item.image if item.image else None,
                "max_purchase_qty": item.custom_max_per_order,
                "holidays": holiday_dates,
                "reviews": review_list,
                "rating": rating,
                "rating_count": rating_count,
                "min_price": min_price,
                "max_price": max_price,
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
