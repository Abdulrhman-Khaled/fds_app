# Copyright (c) 2026, BodyKh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


def _is_api_request():
    """
    Returns True when the request originates from the Flutter API
    (i.e. any whitelisted endpoint under /api/method/fds_app.api.*).
    Dashboard saves come through frappe.desk.* or frappe.client.*
    so they are NOT skipped.
    """
    try:
        path = frappe.request.path if frappe.request else ""
        return "/fds_app.api." in path
    except Exception:
        return False


@frappe.whitelist()
def get_valid_drivers_for_order(service_id, address_id):
    """
    Returns drivers that are:
      1. Linked to the given service (Item.custom_drivers)
      2. Not disabled
      3. Cover the state of the given customer address
    Called from order.js via frappe.call to filter + auto-select the driver field.
    """
    address_state = frappe.db.get_value("Customer Address", address_id, "state")
    if not address_state:
        return {"driver_names": [], "first_driver": None}

    item_doc = frappe.get_doc("Item", service_id)
    service_driver_names = [row.driver for row in (item_doc.custom_drivers or [])]

    if not service_driver_names:
        return {"driver_names": [], "first_driver": None}

    valid_drivers = []
    for driver_name in service_driver_names:
        driver_doc = frappe.get_doc("Drivers", driver_name)
        if driver_doc.disable:
            continue
        driver_states = [str(row.state) for row in (driver_doc.states or [])]
        if str(address_state) in driver_states:
            valid_drivers.append(driver_name)

    return {
        "driver_names": valid_drivers,
        "first_driver": valid_drivers[0] if valid_drivers else None,
    }


class Order(Document):

    def validate(self):
        # Skip all dashboard validations for Flutter API requests
        if _is_api_request():
            return
        self.validate_driver_for_state_and_service()

    def validate_driver_for_state_and_service(self):
        """
        Driver must be linked to the service (via Item.custom_drivers)
        and must cover the state from the selected customer address.
        Only runs on dashboard saves, never on API requests.
        """
        if not self.driver:
            return

        if not self.address:
            frappe.throw(_("Please select a Customer Address before assigning a driver."))

        if not self.service:
            frappe.throw(_("Please select a Service before assigning a driver."))

        # Get the state from the customer address
        address_state = frappe.db.get_value("Customer Address", self.address, "state")
        if not address_state:
            frappe.throw(
                _("The selected address has no State assigned. Please update the address first.")
            )

        # Get the item doc for the selected service
        item_doc = frappe.get_doc("Item", self.service)

        # Collect drivers linked to this service
        service_driver_names = [
            row.driver for row in (item_doc.custom_drivers or [])
        ]

        if not service_driver_names:
            frappe.throw(
                _("The service <b>{0}</b> has no drivers assigned to it.").format(item_doc.item_name)
            )

        if self.driver not in service_driver_names:
            frappe.throw(
                _("Driver <b>{0}</b> is not assigned to service <b>{1}</b>.").format(
                    self.driver, item_doc.item_name
                )
            )

        # Check that the assigned driver covers the address state
        driver_doc = frappe.get_doc("Drivers", self.driver)

        if driver_doc.disable:
            frappe.throw(
                _("Driver <b>{0}</b> is currently disabled.").format(driver_doc.driver_name)
            )

        driver_states = [str(row.state) for row in (driver_doc.states or [])]

        if str(address_state) not in driver_states:
            state_name = frappe.db.get_value("State", address_state, "name_en") or address_state
            frappe.throw(
                _("Driver <b>{0}</b> does not cover the state <b>{1}</b> of the selected address.").format(
                    driver_doc.driver_name, state_name
                )
            )