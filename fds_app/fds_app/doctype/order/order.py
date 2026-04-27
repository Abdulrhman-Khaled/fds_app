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
    address_state = frappe.db.get_value("Customer Address", str(address_id), "state")
    if not address_state:
        return {"driver_names": [], "first_driver": None}

    address_state_name = frappe.db.get_value("State", address_state, "name_en")
    if not address_state_name:
        return {"driver_names": [], "first_driver": None}

    item_doc = frappe.get_doc("Item", service_id)

    valid_drivers = []
    for row in (item_doc.custom_drivers or []):
        is_disabled = frappe.db.get_value("Drivers", row.driver, "disable")
        if is_disabled:
            continue

        match = frappe.db.exists("States Table", {
            "parent": row.driver,
            "parentfield": "states",
            "name_en": address_state_name
        })

        if match:
            valid_drivers.append(row.driver)

    return {
        "driver_names": valid_drivers,
        "first_driver": valid_drivers[0] if valid_drivers else None,
    }


@frappe.whitelist()
def get_variation_price(service_id, variation_id):
    item_doc = frappe.get_doc("Item", service_id)
    for row in (item_doc.custom_slots_and_variations_table or []):
        if str(row.variation) == str(variation_id):
            return row.price
    return 0


class Order(Document):

    def validate(self):
        if _is_api_request():
            return
        self.calculate_total_price()
        self.validate_driver()

    def calculate_total_price(self):
        if self.service_order:
            # Need service + variation to get price from slots table
            if not self.service or not self.variation:
                return
            item_doc = frappe.get_doc("Item", self.service)
            for row in (item_doc.custom_slots_and_variations_table or []):
                if str(row.variation) == str(self.variation):
                    self.total_price = row.price
                    return
        else:
            # Use custom_fixed_price from each item as rate
            total = 0
            for row in (self.services or []):
                fixed_price = frappe.db.get_value("Item", row.item_code, "custom_fixed_price") or 0
                row.rate = fixed_price
                row.amount = fixed_price * (row.qty or 1)
                total += row.amount
            self.total_price = total

    def validate_driver(self):
        if not self.driver or not self.address or not self.service:
            return

        address_state = frappe.db.get_value("Customer Address", str(self.address), "state")
        address_state_name = frappe.db.get_value("State", address_state, "name_en") if address_state else None

        item_doc = frappe.get_doc("Item", self.service)
        service_drivers = [r.driver for r in (item_doc.custom_drivers or [])]

        if self.driver not in service_drivers:
            frappe.throw(_("Driver is not assigned to this service."))

        match = frappe.db.exists("States Table", {
            "parent": self.driver,
            "parentfield": "states",
            "name_en": address_state_name
        })

        if not match:
            frappe.throw(_("Driver does not cover the selected address state."))