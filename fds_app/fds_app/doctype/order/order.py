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
        # Query the child table directly — avoids None values from doc.states
        driver_states = frappe.db.get_all(
            "States Table",
            filters={"parent": row.driver, "parenttype": "Drivers"},
            pluck="state"
        )
        driver_states = [str(s) for s in driver_states]

        if address_state in driver_states:
            is_disabled = frappe.db.get_value("Drivers", row.driver, "disable")
            if not is_disabled:
                valid_drivers.append(row.driver)

    return {
        "driver_names": valid_drivers,
        "first_driver": valid_drivers[0] if valid_drivers else None,
    }


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

        driver_states = frappe.db.get_all(
            "States Table",
            filters={"parent": self.driver, "parenttype": "Drivers"},
            pluck="state"
        )
        driver_states = [str(s) for s in driver_states]

        if address_state not in driver_states:
            frappe.throw(_("Driver does not cover the selected address state."))
