# Copyright (c) 2025, ITQAN and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

class DriverLog(Document):

    def before_save(self):
        self.calculate_total_from_child()
        self.calculate_difference()

    def calculate_total_from_child(self):
        total = 0

        for row in self.finance_info or []:
            total += row.amount or 0

        self.total = total

    def calculate_difference(self):
        self.difference = (self.total or 0) - (self.expenses or 0)
