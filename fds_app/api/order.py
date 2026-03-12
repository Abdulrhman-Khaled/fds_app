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
            time_from = str(row.get("from")) if row.get("from") else None
            time_to = str(row.to) if row.to else None

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