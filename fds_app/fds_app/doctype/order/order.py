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


def _time_to_ampm(time_str):
    if not time_str:
        return ""
    parts = str(time_str).split(":")
    hours = int(parts[0])
    minutes = parts[1] if len(parts) > 1 else "00"
    period = "PM" if hours >= 12 else "AM"
    display_hours = hours % 12 or 12
    return f"{display_hours}:{minutes} {period}"


def _slot_label_from_times(time_from, time_to):
    """Build the AM/PM label like: 8:00 AM : 12:00 PM"""
    return f"{_time_to_ampm(time_from)} : {_time_to_ampm(time_to)}"


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
def get_available_slots(service_id, variation_id, order_date):
    item_doc = frappe.get_doc("Item", service_id)

    available_slots = []
    for row in (item_doc.custom_slots_and_variations_table or []):
        if str(row.variation) != str(variation_id):
            continue

        time_slot = f"{row.get('from')} - {row.to}"

        booked = frappe.db.count("Order", {
            "service": service_id,
            "variation": variation_id,
            "data_lnrd": time_slot,
            "order_date": order_date,
            "status": ["not in", ["cancelled"]]
        })

        if booked < (row.max_per_day or 0):
            available_slots.append({
                "label": row.time_ampm,
                "time_slot": time_slot,
                "price": row.price or 0
            })

    return available_slots


@frappe.whitelist()
def create_sales_invoice(order_id):
    order = frappe.get_doc("Order", order_id)

    company = frappe.defaults.get_global_default("company")
    income_account = frappe.db.get_value("Company", company, "default_income_account")
    cost_center = frappe.db.get_value("Company", company, "cost_center")

    items = []

    if order.service_order:
        item_name = frappe.db.get_value("Item", order.service, "item_name")
        items.append({
            "item_code": order.service,
            "item_name": item_name,
            "qty": 1,
            "rate": order.total_price or 0,
            "income_account": income_account,
            "cost_center": cost_center,
        })
    else:
        for row in (order.services or []):
            items.append({
                "item_code": row.item_code,
                "item_name": row.item_name,
                "qty": row.qty or 1,
                "rate": row.rate or 0,
                "income_account": income_account,
                "cost_center": cost_center,
            })

    invoice = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": order.customer,
        "company": company,
        "items": items,
    })

    invoice.insert(ignore_permissions=True)
    frappe.db.commit()

    return invoice.name


class Order(Document):

    def validate(self):
        if _is_api_request():
            return
        self.calculate_total_price()
        self.validate_driver()

        if self.status == "cancelled":
            frappe.enqueue(
                "frappe.client.delete",
                doctype="Order",
                name=self.name,
                enqueue_after_commit=True
            )

    def after_save(self):
        if self.status == "cancelled":
            frappe.delete_doc("Order", self.name, ignore_permissions=True)

    def calculate_total_price(self):
        if self.service_order:
            if not self.service or not self.variation or not self.data_lnrd:
                return
            item_doc = frappe.get_doc("Item", self.service)
            for row in (item_doc.custom_slots_and_variations_table or []):
                time_slot = f"{row.get('from')} - {row.to}"
                if str(row.variation) == str(self.variation) and time_slot == self.data_lnrd:
                    self.total_price = row.price
                    return
        else:
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

        # if self.driver not in service_drivers:
        #     frappe.throw(_("Driver is not assigned to this service."))

        match = frappe.db.exists("States Table", {
            "parent": self.driver,
            "parentfield": "states",
            "name_en": address_state_name
        })

        if not match:
            frappe.throw(_("Driver does not cover the selected address state."))