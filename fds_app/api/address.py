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
def get_regions(**kwargs):
    try:
        regions = frappe.get_all("Region", filters={"disable": 0}, fields=["name_en", "name_ar"])

        data = []
        for r in regions:
            branch_data = {
                "id": r.id,
                "name_en": r.name_en,
                "name_ar": r.name_ar
            }
            data.append(branch_data)

        frappe.response["status"] = True
        frappe.response["message"] = "region list"
        frappe.response["data"] = data

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Region List Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []