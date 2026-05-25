odoo.define('kassa_pos.ThemeToggle', function (require) {
    'use strict';

    const { Component } = owl;
    const { useState } = owl.hooks;
    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');

    class ThemeToggle extends PosComponent {
        constructor() {
            super(...arguments);
            this.state = useState({
                isLightTheme: false
            });
        }

        mounted() {
            // Check if light theme was previously selected
            const savedTheme = localStorage.getItem('pos-theme');
            if (savedTheme === 'light') {
                this.state.isLightTheme = true;
                document.body.classList.add('light-theme');
            }
            this.addToggleButton();
        }

        addToggleButton() {
            // Create the toggle button
            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'theme-toggle-btn';
            toggleBtn.innerHTML = this.state.isLightTheme ? '🌙' : '☀️';
            toggleBtn.title = this.state.isLightTheme ? 'Switch to Dark Theme' : 'Switch to Light Theme';

            // Add click event
            toggleBtn.addEventListener('click', () => {
                this.toggleTheme();
            });

            // Add to DOM
            document.body.appendChild(toggleBtn);
        }

        toggleTheme() {
            this.state.isLightTheme = !this.state.isLightTheme;

            if (this.state.isLightTheme) {
                document.body.classList.add('light-theme');
                localStorage.setItem('pos-theme', 'light');
            } else {
                document.body.classList.remove('light-theme');
                localStorage.setItem('pos-theme', 'dark');
            }

            // Update button icon
            const toggleBtn = document.querySelector('.theme-toggle-btn');
            if (toggleBtn) {
                toggleBtn.innerHTML = this.state.isLightTheme ? '🌙' : '☀️';
                toggleBtn.title = this.state.isLightTheme ? 'Switch to Dark Theme' : 'Switch to Light Theme';
            }
        }
    }

    ThemeToggle.template = 'ThemeToggle';

    Registries.Component.add(ThemeToggle);

    return ThemeToggle;
});