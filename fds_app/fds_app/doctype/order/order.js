// Copyright (c) 2026, BodyKh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {

    refresh(frm) {
        update_driver_filter(frm);
    },

    address(frm) {
        update_driver_filter(frm);
    },

    service(frm) {
        update_driver_filter(frm);
    },

});


function update_driver_filter(frm) {
    const service = frm.doc.service;
    const address = frm.doc.address;

    // Clear driver if service or address is missing
    if (!service || !address) {
        frm.set_value("driver", null);
        frm.set_query("driver", () => ({ filters: { name: "__none__" } }));
        return;
    }

    // Fetch the state from the selected address and valid drivers for service + state
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

                // Restrict the driver field to only valid drivers
                frm.set_query("driver", () => ({
                    filters: [["Drivers", "name", "in", driver_names]]
                }));

                // Auto-select the first valid driver
                frm.set_value("driver", first_driver);
            }
        }
    });
}