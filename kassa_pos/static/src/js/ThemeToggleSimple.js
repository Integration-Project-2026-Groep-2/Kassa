(function() {
    'use strict';

    // Wait for DOM to be ready
    function initThemeToggle() {
        // Check if button already exists
        if (document.querySelector('.theme-toggle-btn')) {
            return;
        }

        // Check localStorage for saved theme preference
        const savedTheme = localStorage.getItem('pos-theme');
        let isLightTheme = savedTheme === 'light';

        // Apply saved theme
        if (isLightTheme) {
            document.body.classList.add('light-theme');
        } else {
            document.body.classList.remove('light-theme');
        }

        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'theme-toggle-btn';
        toggleBtn.innerHTML = isLightTheme ? '🌙' : '☀️';
        toggleBtn.title = isLightTheme ? 'Schakel naar donker thema' : 'Schakel naar licht thema';

        // Add click event
        toggleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            isLightTheme = !isLightTheme;

            if (isLightTheme) {
                document.body.classList.add('light-theme');
                localStorage.setItem('pos-theme', 'light');
                toggleBtn.innerHTML = '🌙';
                toggleBtn.title = 'Schakel naar donker thema';
            } else {
                document.body.classList.remove('light-theme');
                localStorage.setItem('pos-theme', 'dark');
                toggleBtn.innerHTML = '☀️';
                toggleBtn.title = 'Schakel naar licht thema';
            }
        });

        // Add to DOM
        document.body.appendChild(toggleBtn);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initThemeToggle);
    } else {
        initThemeToggle();
    }

    // Also initialize after a short delay to catch dynamic content
    setTimeout(initThemeToggle, 500);
    setTimeout(initThemeToggle, 1500);
})();
