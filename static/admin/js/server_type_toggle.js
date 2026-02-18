/**
 * Toggle field visibility on the PostgresServer add/change form
 * based on the selected server_type (docker vs remote).
 *
 * Docker:  host/admin_username are auto-filled and dimmed.
 * Remote:  host/admin_username are editable, port keeps whatever the admin sets.
 */
(function () {
    'use strict';

    function applyToggle() {
        var select = document.getElementById('id_server_type');
        if (!select) return;

        var hostRow    = document.querySelector('.field-host');
        var userRow    = document.querySelector('.field-admin_username');
        var hostInput  = document.getElementById('id_host');
        var userInput  = document.getElementById('id_admin_username');

        function toggle() {
            var isDocker = select.value === 'docker';

            if (hostRow) {
                // For Docker: pre-fill and make readonly
                if (isDocker) {
                    if (hostInput) {
                        hostInput.value = 'localhost';
                        hostInput.readOnly = true;
                        hostInput.style.opacity = '0.6';
                    }
                    if (userInput) {
                        userInput.value = 'postgres';
                        userInput.readOnly = true;
                        userInput.style.opacity = '0.6';
                    }
                } else {
                    if (hostInput) {
                        hostInput.readOnly = false;
                        hostInput.style.opacity = '1';
                        if (hostInput.value === 'localhost') hostInput.value = '';
                    }
                    if (userInput) {
                        userInput.readOnly = false;
                        userInput.style.opacity = '1';
                    }
                }
            }
        }

        select.addEventListener('change', toggle);
        toggle();  // Run once on load
    }

    // Run when the DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyToggle);
    } else {
        applyToggle();
    }
})();
