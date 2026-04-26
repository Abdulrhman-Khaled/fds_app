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
    address_state = frappe.db.get_value("Customer Address", address_id, "state")
    if not address_state:
        return {"driver_names": [], "first_driver": None}

    item_doc = frappe.get_doc("Item", service_id)

    valid_drivers = []
    for row in (item_doc.custom_drivers or []):
        driver_doc = frappe.get_doc("Drivers", row.driver)
        if driver_doc.disable:
            continue
        driver_states = [str(r.state) for r in (driver_doc.states or [])]
        if str(address_state) in driver_states:
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

        address_state = frappe.db.get_value("Customer Address", self.address, "state")
        item_doc = frappe.get_doc("Item", self.service)
        service_drivers = [r.driver for r in (item_doc.custom_drivers or [])]

        if self.driver not in service_drivers:
            frappe.throw(_("Driver is not assigned to this service."))

        driver_doc = frappe.get_doc("Drivers", self.driver)
        driver_states = [str(r.state) for r in (driver_doc.states or [])]

        if str(address_state) not in driver_states:
            frappe.throw(_("Driver does not cover the selected address state."))