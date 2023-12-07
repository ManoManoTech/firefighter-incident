import 'htmx.org';
import 'hyperscript.org';
import 'htmx.org/dist/ext/alpine-morph';
import 'htmx.org/dist/ext/head-support';

import Alpine from 'alpinejs';
import collapse from '@alpinejs/collapse';
import focus from '@alpinejs/focus'
import morph from '@alpinejs/morph'

// XXX Enable htmx debug ext automatically in DEV

window.Alpine = Alpine;
window.htmx = htmx;

Alpine.plugin(collapse);
Alpine.plugin(morph);
Alpine.plugin(focus);
Alpine.start();


document.addEventListener('DOMContentLoaded', () => {
    console.log("FireFighter JS Loaded");
});
