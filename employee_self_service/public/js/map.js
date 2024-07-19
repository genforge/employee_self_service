let script_ = document.createElement('script');
const apiKey = 'AIzaSyDhKqaOvHzbVviz67ZPHjT3UEba2DNSzlw';
script_.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&callback=initMap`;
script_.async = true;
script_.defer = true;

window.initMap = function() {
    console.log('Google Maps API loaded successfully');
};

script_.onerror = function() {
    console.error('Error loading Google Maps API');
};

document.head.appendChild(script_);