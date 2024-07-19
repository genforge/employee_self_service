function initAutocomplete(frm) {
    let autocomplete;

    
    const inputHtml = '<label class="control-label" style="padding-right: 0px;">Search Address</label><input class="form-control" placeholder="Search a location" id="autocomplete-address-source" style="height: 30px; margin-bottom: 5px;">';
    $(frm.fields_dict.custom_address_search.wrapper).html(inputHtml);

    
    setTimeout(() => {
        const inputElement = document.getElementById('autocomplete-address-source');
        if (inputElement) {
            autocomplete = new google.maps.places.Autocomplete(inputElement, { types: ["geocode"] });

            autocomplete.addListener("place_changed", function() {
                const place = autocomplete.getPlace();
                if (place.geometry) {
                    const lat = place.geometry.location.lat();
                    const lng = place.geometry.location.lng();
                    frm.set_value('latitude', lat);
                    frm.set_value('longitude', lng);
                    frm.set_value('custom_address', place.formatted_address);
                    frm.save();
                } else {
                    frappe.msgprint(__('No details available for input: ' + place.name));
                }
            });
        }
    }, 500);
}

frappe.ui.form.on('Branch', {
    refresh: function(frm) {
        console.log("Initializing autocomplete address field");
        initAutocomplete(frm);
    },
    custom_address: function(frm) {
        const address = frm.doc.custom_address;
        if (address) {
            geocodeAddress(address, (error, location) => {
                if (error) {
                    frappe.msgprint(__('Error getting coordinates: ' + error));
                } else {
                    frm.set_value('latitude', location.lat);
                    frm.set_value('longitude', location.lng);
                    frm.save();
                }
            });
        }
    }
});

