frappe.ui.form.on('Item', {
    refresh: function(frm) {
        frm.doc.slots_variations_table && frm.doc.slots_variations_table.forEach((row) => {
            update_time_ampm(frm, row.doctype, row.name);
        });
    }
});

frappe.ui.form.on('Slots Variations Table', {
    from: function(frm, cdt, cdn) {
        update_time_ampm(frm, cdt, cdn);
    },
    to: function(frm, cdt, cdn) {
        update_time_ampm(frm, cdt, cdn);
    }
});

function update_time_ampm(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let from_ampm = convert_to_ampm(row.from);
    let to_ampm = convert_to_ampm(row.to);

    if (from_ampm || to_ampm) {
        let time_ampm = `${from_ampm || '--'} : ${to_ampm || '--'}`;
        frappe.model.set_value(cdt, cdn, 'time_ampm', time_ampm);
    }
}

function convert_to_ampm(time_str) {
    if (!time_str) return '';

    let parts = time_str.split(':');
    let hours = parseInt(parts[0]);
    let minutes = parts[1] || '00';

    let period = hours >= 12 ? 'PM' : 'AM';
    let display_hours = hours % 12 || 12;

    return `${display_hours}:${minutes} ${period}`;
}