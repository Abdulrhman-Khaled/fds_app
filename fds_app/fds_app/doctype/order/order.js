// Copyright (c) 2026, BodyKh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {

    refresh(frm) {
        update_driver_filter(frm);
    },

    service(frm) {
        frm.set_value("variation", null);
        frm.set_value("data_lnrd", null);
        frm.set_value("order_date", null);
        update_driver_filter(frm);
        calculate_total(frm);
    },

    order_date(frm) {
        frm.set_value("data_lnrd", null);
        update_time_slots(frm);
    },

    variation(frm) {
        frm.set_value("data_lnrd", null);
        update_time_slots(frm);
        calculate_total(frm);
    },

    address(frm) {
        update_driver_filter(frm);
    },

    service_order(frm) {
        frm.set_value("total_price", 0);
    },

});

// When a row is added or item_code changes in services table
frappe.ui.form.on("Sales Invoice Item", {

    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code) return;

        frappe.db.get_value("Item", row.item_code, "custom_fixed_price", (r) => {
            frappe.model.set_value(cdt, cdn, "rate", r.custom_fixed_price || 0);
            frappe.model.set_value(cdt, cdn, "amount", (r.custom_fixed_price || 0) * (row.qty || 1));
            calculate_total(frm);
        });
    },

    qty(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "amount", (row.rate || 0) * (row.qty || 1));
        calculate_total(frm);
    },

    services_remove(frm) {
        calculate_total(frm);
    },

});


function update_time_slots(frm) {
    const service   = frm.doc.service;
    const variation = frm.doc.variation;
    const date      = frm.doc.order_date;

    // Need all three to fetch slots
    if (!service || !variation || !date) return;

    frappe.call({
        method: "fds_app.fds_app.doctype.order.order.get_available_slots",
        args: { service_id: service, variation_id: variation, order_date: date },
        callback(r) {
            const slots = r.message || [];

            if (slots.length === 0) {
                frm.set_value("data_lnrd", null);
                frappe.msgprint({
                    title: __("No Available Slots"),
                    message: __("All slots are fully booked for this variation on the selected date."),
                    indicator: "orange"
                });
                return;
            }

            // Build select options string for the field
            const options = slots.join("\n");
            frm.set_df_property("data_lnrd", "fieldtype", "Select");
            frm.set_df_property("data_lnrd", "options", options);
            frm.set_value("data_lnrd", slots[0]);
            frm.refresh_field("data_lnrd");
        }
    });
}


function calculate_total(frm) {
    if (frm.doc.service_order) {
        if (!frm.doc.service || !frm.doc.variation) {
            frm.set_value("total_price", 0);
            return;
        }
        frappe.call({
            method: "fds_app.fds_app.doctype.order.order.get_variation_price",
            args: { service_id: frm.doc.service, variation_id: frm.doc.variation },
            callback(r) {
                frm.set_value("total_price", r.message || 0);
            }
        });
    } else {
        let total = 0;
        (frm.doc.services || []).forEach(row => {
            total += (row.rate || 0) * (row.qty || 1);
        });
        frm.set_value("total_price", total);
    }
}


function update_driver_filter(frm) {
    const service = frm.doc.service;
    const address = frm.doc.address;

    if (!service || !address) {
        frm.set_value("driver", null);
        frm.set_query("driver", () => ({ filters: { name: "__none__" } }));
        return;
    }

    frappe.call({
        method: "fds_app.fds_app.doctype.order.order.get_valid_drivers_for_order",
        args: { service_id: service, address_id: address },
        callback(r) {
            if (!r.exc && r.message) {
                const driver_names = r.message.driver_names || [];
                const first_driver = r.message.first_driver || null;

                if (driver_names.length === 0) {
                    frm.set_value("driver", null);
                    frappe.msgprint({
                        title: __("No Drivers Available"),
                        message: __("No available driver found for the selected service and address state."),
                        indicator: "orange"
                    });
                    frm.set_query("driver", () => ({ filters: { name: "__none__" } }));
                    return;
                }

                frm.set_query("driver", () => ({
                    filters: [["Drivers", "name", "in", driver_names]]
                }));

                frm.set_value("driver", first_driver);
            }
        }
    });
}