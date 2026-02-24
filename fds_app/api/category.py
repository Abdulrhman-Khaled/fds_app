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
def get_home_data():
    try:
        base_url = frappe.utils.get_url()

        categories = frappe.get_all(
            "Item Group",
            filters={"is_group": 1},
            fields=["name", "custom_name_ar", "image"],
            order_by="name asc"
        )

        category_list = []
        for c in categories:
            category_list.append({
                "id": c.name,
                "name_en": c.name,
                "name_ar": c.custom_name_ar,
                "image":  base_url + c.image if c.image else None
            })

        sliders = frappe.get_all(
            "Sliders",
            fields=["name", "name1", "image"],
            order_by="modified desc"
        )

        slider_list = []
        for s in sliders:
            image_url = None
            if s.image:
                image_url = base_url + s.image

            slider_list.append({
                "id": s.name,
                "name": s.name1,
                "image": image_url
            })

        frappe.response["status"] = True
        frappe.response["message"] = "Home data fetched successfully"
        frappe.response["data"] = {
            "categories": category_list,
            "sliders": slider_list
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Home API Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []