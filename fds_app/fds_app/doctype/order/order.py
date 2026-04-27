# Copyright (c) 2026, BodyKh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


def _is_api_request():
    try:
        return "/fds_app.api." in frappe.request.path
    except Exception:
        return False


@frappe.whitelist()
def get_valid_drivers_for_order(service_id, address_id):
    address_state = str(frappe.db.get_value("Customer Address", str(address_id), "state") or "")
    if not address_state:
        return {"driver_names": [], "first_driver": None}

    item_doc = frappe.get_doc("Item", service_id)

    valid_drivers = []
    for row in (item_doc.custom_drivers or []):
        # Fetch all columns to see what's actually stored
        raw = frappe.db.sql(
            "SELECT * FROM `tabStates Table` WHERE parent = %s AND parentfield = 'states' LIMIT 3",
            str(row.driver),
            as_dict=True
        )
        frappe.log_error(str(raw[0] if raw else "NO ROWS"), "states_table_raw")

    return {"driver_names": [], "first_driver": None}


class Order(Document):

    def validate(self):
        if _is_api_request():
            return
        self.validate_driver()

    def validate_driver(self):
        if not self.driver or not self.address or not self.service:
            return

        address_state = str(frappe.db.get_value("Customer Address", str(self.address), "state") or "")
        item_doc = frappe.get_doc("Item", self.service)
        service_drivers = [r.driver for r in (item_doc.custom_drivers or [])]

        if self.driver not in service_drivers:
            frappe.throw(_("Driver is not assigned to this service."))

        driver_states = frappe.db.sql(
            "SELECT state FROM `tabStates Table` WHERE parent = %s AND parentfield = 'states'",
            str(self.driver),
            as_dict=True
        )
        driver_state_values = [str(r.state) for r in driver_states]

        if address_state not in driver_state_values:
            frappe.throw(_("Driver does not cover the selected address state."))