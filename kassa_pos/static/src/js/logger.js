/** @odoo-module **/

function _send(level, args) {
    const data = args
        .map((a) => (a !== null && typeof a === "object" ? JSON.stringify(a) : String(a)))
        .join(" ");
    fetch("/kassa/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level, data }),
    }).catch(() => {});
}

export const logger = {
    debug: (...a) => { console.debug(...a); _send("DEBUG", a); },
    info:  (...a) => { console.info(...a);  _send("INFO",  a); },
    log:   (...a) => { console.log(...a);   _send("INFO",  a); },
    warn:  (...a) => { console.warn(...a);  _send("WARN",  a); },
    error: (...a) => { console.error(...a); _send("ERROR", a); },
};
