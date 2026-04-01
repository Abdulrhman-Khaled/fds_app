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
def check_business_eligibility(customer_id=None):
    try:
        if not customer_id:
            frappe.response["status"] = False
            frappe.response["message"] = "customer_id is required"
            frappe.response["data"] = None
            return

        if not frappe.db.exists("Customer", customer_id):
            frappe.response["status"] = False
            frappe.response["message"] = "Customer not found"
            frappe.response["data"] = None
            return

        customer_doc = frappe.get_doc("Customer", customer_id)

        missing_fields = []

        if not customer_doc.tax_id:
            missing_fields.append("tax_id")
        if not customer_doc.custom_vat_registration_number:
            missing_fields.append("vat_registration_number")
        if not customer_doc.customer_primary_address:
            missing_fields.append("primary_address")


        if customer_doc.customer_primary_address:
            if not frappe.db.exists("Address", customer_doc.customer_primary_address):
                missing_fields.append("primary_address_not_found")
            else:
                address_doc = frappe.get_doc("Address", customer_doc.customer_primary_address)

                if not address_doc.address_line1:
                    missing_fields.append("address_line1")
                if not address_doc.city:
                    missing_fields.append("city")
                if not address_doc.country:
                    missing_fields.append("country")
                if not address_doc.state:
                    missing_fields.append("state")
                if not address_doc.pincode:
                    missing_fields.append("pincode")
                if not address_doc.email_id:
                    missing_fields.append("email")
                if not address_doc.phone:
                    missing_fields.append("phone")

        is_eligible = len(missing_fields) == 0

        frappe.response["status"] = True
        frappe.response["message"] = "Eligible for business" if is_eligible else "Profile incomplete"
        frappe.response["data"] = {
            "customer_id": customer_id,
            "is_eligible": 1 if is_eligible else 0,
            "missing_fields": missing_fields
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Check Business Eligibility Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None
