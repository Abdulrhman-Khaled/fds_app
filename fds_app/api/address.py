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
        regions = frappe.get_all("Region", filters={"disable": 0}, fields=["*"])

        data = []
        for r in regions:
            region_data = {
                "id": r.name,
                "name_en": r.name_en,
                "name_ar": r.name_ar
            }
            data.append(region_data)

        frappe.response["status"] = True
        frappe.response["message"] = "Regions List"
        frappe.response["data"] = data

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Region List Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def get_states(region=None):
    try:
        if not region:
            frappe.response["status"] = False
            frappe.response["message"] = "Region is required"
            frappe.response["data"] = []
            return

        states = frappe.get_all("State", filters={"disable": 0, "region": region}, fields=["*"])

        data = []
        for s in states:
            state_data = {
                "id": s.name,
                "name_en": s.name_en,
                "name_ar": s.name_ar,
                "region": s.region.name
            }
            data.append(state_data)

        frappe.response["status"] = True
        frappe.response["message"] = "States List"
        frappe.response["data"] = data

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="States List Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []