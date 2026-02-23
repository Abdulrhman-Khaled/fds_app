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
                "region": s.region
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

@frappe.whitelist(allow_guest=True)
def create_customer_address(
    first_name,
    last_name,
    region,
    state,
    customer,
    address,
    primary=0,
    lat_lng=None
):
    try:
        if not customer:
            frappe.response["status"] = False
            frappe.response["message"] = "Customer is required"
            frappe.response["data"] = []
            return

        if primary == 1:
            old_addresses = frappe.get_all(
                "Customer Address",
                filters={"customer": customer, "primary": 1},
                fields=["name"]
            )

            for addr in old_addresses:
                frappe.db.set_value("Customer Address", addr.name, "primary", 0)

        doc = frappe.get_doc({
            "doctype": "Customer Address",
            "first_name": first_name,
            "last_name": last_name,
            "region": region,
            "state": state,
            "customer": customer,
            "address": address,
            "primary": primary,
            "lat_lng": lat_lng
        })

        doc.insert(ignore_permissions=True)

        customer_doc = frappe.get_doc("Customer", customer)

        customer_doc.append("custom_address", {
            "address": doc.name,
        })

        customer_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Customer Address Created Successfully"
        frappe.response["data"] = {
            "id": doc.name
        }

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Create Customer Address Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def update_customer_address(
    address_id,
    first_name=None,
    last_name=None,
    region=None,
    state=None,
    customer=None,
    address=None,
    primary=None,
    lat_lng=None
):
    try:
        if not address_id:
            frappe.response["status"] = False
            frappe.response["message"] = "Address ID is required"
            frappe.response["data"] = []
            return

        doc = frappe.get_doc("Customer Address", address_id)

        if primary is not None and primary == 1:
            old_addresses = frappe.get_all(
                "Customer Address",
                filters={"customer": customer, "primary": 1},
                fields=["name"]
            )

            for addr in old_addresses:
                frappe.db.set_value("Customer Address", addr.name, "primary", 0)

        if first_name is not None:
            doc.first_name = first_name
        if last_name is not None:
            doc.last_name = last_name
        if region is not None:
            doc.region = region
        if state is not None:
            doc.state = state
        if address is not None:
            doc.address = address
        if primary is not None:
            doc.primary = primary
        if lat_lng is not None:
            doc.lat_lng = lat_lng

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Customer Address Updated Successfully"
        frappe.response["data"] = {
            "id": doc.name
        }

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Update Customer Address Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def delete_customer_address(address_id):
    try:
        if not address_id:
            frappe.response["status"] = False
            frappe.response["message"] = "Address ID is required"
            frappe.response["data"] = []
            return

        address_doc = frappe.get_doc("Customer Address", address_id)
        customer_name = address_doc.customer
        was_primary = address_doc.primary

        rows = frappe.get_all(
            "Customer Address Table",
            filters={"address": address_id},
            fields=["name"]
        )

        for row in rows:
            frappe.delete_doc(
                "Customer Address Table",
                row.name,
                force=True
            )

        frappe.delete_doc("Customer Address", address_id, ignore_permissions=True)

        if was_primary:
            another_address = frappe.get_all(
                "Customer Address",
                filters={"customer": customer_name},
                fields=["name"],
                limit=1
            )

            if another_address:
                frappe.db.set_value(
                    "Customer Address",
                    another_address[0].name,
                    "primary",
                    1
                )

        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Customer Address Deleted Successfully"
        frappe.response["data"] = []

    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Delete Customer Address Error"
        )
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []