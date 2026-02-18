/**
 * Toggle "Create new database" fields vs "existing database" dropdown
 * on the DatabaseAssignment add page.
 */
(function () {
    'use strict';

    function applyToggle() {
        var checkbox = document.getElementById('id_create_new_database');
        if (!checkbox) return;

        var serverRow   = document.querySelector('.field-server');
        var dbNameRow   = document.querySelector('.field-database_name');
        var existingRow = document.querySelector('.field-database');

        function toggle() {
            var createNew = checkbox.checked;

            // Show/hide rows
            if (serverRow)   serverRow.style.display   = createNew ? '' : 'none';
            if (dbNameRow)   dbNameRow.style.display   = createNew ? '' : 'none';
            if (existingRow) existingRow.style.display  = createNew ? 'none' : '';
        }

        checkbox.addEventListener('change', toggle);
        toggle();  // Run once on load
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyToggle);
    } else {
        applyToggle();
    }
})();
