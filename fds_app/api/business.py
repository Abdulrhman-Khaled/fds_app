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

        tax_id = customer_doc.tax_id or None
        vat_number = customer_doc.custom_vat_registration_number or None
        primary_address = customer_doc.customer_primary_address or None

        if not tax_id:
            missing_fields.append("tax_id")
        if not vat_number:
            missing_fields.append("vat_registration_number")
        if not primary_address:
            missing_fields.append("primary_address")

        address_line1 = None
        building_number = None
        area = None
        city = None
        country = None
        state = None
        pincode = None
        email = None
        phone = None

        if primary_address:
            if not frappe.db.exists("Address", primary_address):
                missing_fields.append("primary_address_not_found")
            else:
                address_doc = frappe.get_doc("Address", primary_address)

                address_line1 = address_doc.address_line1 or None
                building_number = address_doc.custom_building_number or None
                area = address_doc.custom_area or None
                city = address_doc.city or None
                country = address_doc.country or None
                state = address_doc.state or None
                pincode = address_doc.pincode or None
                email = address_doc.email_id or None
                phone = address_doc.phone or None

                if not address_line1:
                    missing_fields.append("address_line1")
                if not building_number:
                    missing_fields.append("building_number")
                if not area:
                    missing_fields.append("area")
                if not city:
                    missing_fields.append("city")
                if not country:
                    missing_fields.append("country")
                if not state:
                    missing_fields.append("state")
                if not pincode:
                    missing_fields.append("pincode")
                if not email:
                    missing_fields.append("email")
                if not phone:
                    missing_fields.append("phone")

        is_eligible = len(missing_fields) == 0

        frappe.response["status"] = True
        frappe.response["message"] = "Eligible for business" if is_eligible else "Profile incomplete"
        frappe.response["data"] = {
            "customer_id": customer_id,
            "is_eligible": 1 if is_eligible else 0,
            "missing_fields": missing_fields,
            "fields": {
                "company_name": customer_doc.customer_name,
                "tax_id": tax_id,
                "vat_registration_number": vat_number,
                "primary_address": primary_address,
                "address_line1": address_line1,
                "building_number": building_number,
                "area": area,
                "city": city,
                "country": country,
                "state": state,
                "pincode": pincode,
                "email": email,
                "phone": phone,
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Check Business Eligibility Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None

@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_business_profile(
    customer_id=None,
    customer_name=None,
    tax_id=None,
    vat_registration_number=None,
    address_line1=None,
    building_number=None,
    area=None,
    city=None,
    country=None,
    state=None,
    pincode=None,
    email=None,
    phone=None,
):
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

        if customer_name:
            customer_doc.customer_name = customer_name
        if tax_id:
            customer_doc.tax_id = tax_id
        if vat_registration_number:
            customer_doc.custom_vat_registration_number = vat_registration_number

        customer_doc.customer_type = "Company"

        customer_doc.save(ignore_permissions=True)

        if customer_doc.customer_primary_address and frappe.db.exists("Address", customer_doc.customer_primary_address):
            address_doc = frappe.get_doc("Address", customer_doc.customer_primary_address)
        else:
            address_doc = frappe.new_doc("Address")
            address_doc.address_title = customer_doc.customer_name
            address_doc.address_type = "Billing"
            address_doc.append("links", {
                "link_doctype": "Customer",
                "link_name": customer_id
            })

        if address_line1:
            address_doc.address_line1 = address_line1
        if building_number:
            address_doc.custom_building_number = building_number
        if area:
            address_doc.custom_area = area
        if city:
            address_doc.city = city
        if country:
            address_doc.country = country
        if state:
            address_doc.state = state
        if pincode:
            address_doc.pincode = pincode
        if email:
            address_doc.email_id = email
        if phone:
            address_doc.phone = phone

        address_doc.save(ignore_permissions=True)
        
        customer_doc.reload()
        customer_doc.customer_primary_address = address_doc.name
        customer_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Business profile updated successfully"
        frappe.response["data"] = {
            "customer_id": customer_id,
            "customer_name": customer_doc.customer_name,
            "customer_type": customer_doc.customer_type,
            "tax_id": customer_doc.tax_id,
            "vat_registration_number": customer_doc.custom_vat_registration_number,
            "primary_address": customer_doc.customer_primary_address,
            "address_line1": address_doc.address_line1,
            "building_number": address_doc.custom_building_number,
            "area": address_doc.custom_area,
            "city": address_doc.city,
            "country": address_doc.country,
            "state": address_doc.state,
            "pincode": address_doc.pincode,
            "email": address_doc.email_id,
            "phone": address_doc.phone,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Business Profile Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = None

@frappe.whitelist(allow_guest=True)
def get_business_items(category_id=None, search=None):
    try:
        if not category_id:
            frappe.response["status"] = False
            frappe.response["message"] = "category_id is required"
            frappe.response["data"] = []
            return

        base_url = frappe.utils.get_url()

        child_groups = frappe.get_all(
            "Item Group",
            filters={"parent_item_group": category_id},
            fields=["name"]
        )

        group_names = [g.name for g in child_groups] if child_groups else [category_id]

        filters = {
            "disabled": 0,
            "item_group": ["in", group_names]
        }

        or_filters = None
        if search:
            or_filters = [
                ["item_name", "like", f"%{search}%"],
                ["custom_item_name_ar", "like", f"%{search}%"]
            ]

        items = frappe.get_all(
            "Item",
            filters=filters,
            or_filters=or_filters,
            fields=["name", "item_name", "custom_item_name_ar", "item_group", "image"]
        )

        item_list = []
        for item in items:
            item_price = frappe.db.get_value(
                "Item Price",
                {"item_code": item.name},
                "price_list_rate",
                order_by="creation asc"
            )
            price = item_price or 0

            item_list.append({
                "id": item.name,
                "name_en": item.item_name,
                "name_ar": item.custom_item_name_ar or "",
                "category": item.item_group,
                "image": base_url + item.image if item.image else None,
                "price": price,
            })

        frappe.response["status"] = True
        frappe.response["message"] = "Items fetched successfully"
        frappe.response["data"] = item_list

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Business Items Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []
