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
def get_items_by_group(item_group):
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
                "custom_holiday_list"
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
                "holidays": holiday_dates
            })

        frappe.response["status"] = True
        frappe.response["message"] = "Items fetched successfully"
        frappe.response["data"] = item_list

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Items By Group Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []
