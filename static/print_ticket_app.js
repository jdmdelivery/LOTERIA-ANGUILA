/**
 * Impresión térmica 58mm: ESC/POS (base64) en APK / HTML en navegador.
 */
(function () {
  function normalizarTexto(texto) {
    return String(texto == null ? "" : texto).replace(/\r\n/g, "\n");
  }

  function extraerTicketId(texto) {
    var m = String(texto || "").match(/ticket\s*[:#]?\s*(\d+)/i);
    if (m) return m[1];
    var el = document.querySelector("[data-ticket-id]");
    if (el) return el.getAttribute("data-ticket-id") || "";
    var path = window.location.pathname || "";
    var m2 = path.match(/\/imprimir_pago\/(\d+)/) ||
      path.match(/\/ticket\/(\d+)/);
    return m2 ? m2[1] : "";
  }

  function obtenerEscPosB64() {
    var el = document.querySelector("[data-escpos-b64]");
    if (!el) return "";
    return String(el.getAttribute("data-escpos-b64") || "").trim();
  }

  function obtenerContenidoHtmlTicket() {
    var box = document.querySelector(".ticket-thermal") || document.querySelector(".ticket");
    if (!box) return "";
    var clone = box.cloneNode(true);
    var rm = clone.querySelectorAll(
      ".no-print, button, .btn, #printBtn, .btn-print-top, pre[data-print-text]"
    );
    for (var i = 0; i < rm.length; i++) {
      rm[i].parentNode.removeChild(rm[i]);
    }
    return clone.innerHTML;
  }

  window.__onAndroidPrintResult = function (result) {
    var ok = result && result.ok;
    var msg = (result && result.message) || "";
    var imp = (result && result.impresora) || "";
    if (ok) {
      console.log("[PRINT_OK] impresora=" + imp + " " + msg);
      return;
    }
    console.error("[PRINT_ERROR] mensaje=" + msg + " impresora=" + imp);
    var box = document.getElementById("printErrorBox");
    if (box) {
      box.style.display = "block";
      box.textContent = "Error imprimiendo: " + msg;
    }
  };

  window.ticketPlainFromEl = function (id) {
    var el = typeof id === "string" ? document.getElementById(id) : id;
    if (!el) return "";
    return normalizarTexto(el.textContent || "");
  };

  window.textoPlanoDesdeHtml = function (html) {
    var div = document.createElement("div");
    div.innerHTML = String(html || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/div>/gi, "\n")
      .replace(/<\/p>/gi, "\n")
      .replace(/<\/tr>/gi, "\n");
    return normalizarTexto(div.textContent || "")
      .split("\n")
      .map(function (linea) {
        return linea.replace(/[ \t]+$/g, "");
      })
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  };

  window.formatearHoraCompacta = function (texto) {
    var s = String(texto == null ? "" : texto);
    return s.replace(/\b(\d{1,2})(\d{2})(am|pm)\b/gi, function (_m, h, mi, ap) {
      return parseInt(h, 10) + ":" + mi + " " + String(ap).toUpperCase();
    });
  };

  window.imprimirTicket = function (texto) {
    texto = normalizarTexto(texto);
    var ticketId = extraerTicketId(texto);
    var escposB64 = obtenerEscPosB64();
    var impresora = "Bluetooth/ESC-POS";

    console.log(
      "[PRINT_START] ticket_id=" + (ticketId || "—") +
      " contenido_length=" + (escposB64 ? escposB64.length : texto.length) +
      " impresora=" + impresora +
      " modo=" + (escposB64 ? "escpos_b64" : "texto")
    );

    if (window.Android) {
      if (escposB64 && typeof Android.printEscPosBase64 === "function") {
        console.log("Imprimiendo ESC/POS base64 vía Android.printEscPosBase64");
        Android.printEscPosBase64(escposB64, ticketId || "");
        return;
      }
      if (typeof Android.printTicket === "function") {
        console.log("Imprimiendo texto vía Android.printTicket");
        Android.printTicket(texto, ticketId || "");
        return;
      }
      if (typeof Android.print === "function") {
        console.log("Imprimiendo texto vía Android.print");
        Android.print(texto);
        return;
      }
      if (typeof Android.logPrint === "function") {
        Android.logPrint("JS", "[PRINT_START] ticket_id=" + ticketId + " len=" + texto.length);
      }
    }

    var htmlTicket = obtenerContenidoHtmlTicket();
    if (!htmlTicket && (!texto || !texto.trim())) {
      var errEmpty = "El ticket está vacío (contenido_length=0)";
      console.error("[PRINT_ERROR] mensaje=" + errEmpty);
      alert("Error imprimiendo:\n" + errEmpty);
      return;
    }

    console.log("Modo navegador (sin Android.print)");
    var win = window.open("", "", "width=240,height=700");
    if (!win || !win.document) {
      console.error("[PRINT_ERROR] mensaje=No se pudo abrir ventana de impresión");
      return;
    }
    var cuerpo = htmlTicket
      ? htmlTicket
      : "<pre>" + texto.replace(/[&<>]/g, function (c) {
          return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c];
        }) + "</pre>";
    win.document.write(
      "<!DOCTYPE html><html><head><meta charset='utf-8'>" +
      "<meta name='viewport' content='width=58mm'>" +
      "<link rel='stylesheet' href='/static/ticket_thermal.css'></head>" +
      "<body class='ticket-body'><div class='ticket ticket-thermal'>" +
      cuerpo +
      "</div></body></html>"
    );
    win.document.close();
    win.focus();
    win.print();
  };

  window.printTicketApp = window.imprimirTicket;

  window.conectarImpresora = function () {
    console.log("Intentando conectar impresora...");
    if (window.Android && typeof Android.connect === "function") {
      Android.connect();
    }
  };

  window.generarTicket = window.generarTicket || function () {
    var pre = document.getElementById("reciboTextoPlano");
    if (pre && pre.textContent && pre.textContent.trim()) {
      return window.ticketPlainFromEl(pre);
    }
    var htmlBox = document.querySelector(".ticket-thermal") || document.querySelector(".ticket");
    if (htmlBox) {
      var plain = window.textoPlanoDesdeHtml(obtenerContenidoHtmlTicket());
      if (plain) return plain;
    }
    var esc = obtenerEscPosB64();
    if (esc) {
      var el = document.querySelector("[data-print-text]") || document.getElementById("reciboTextoPlano");
      if (el) return window.ticketPlainFromEl(el);
    }
    return "";
  };

  window.imprimir = window.imprimir || function () {
    window.imprimirTicket(window.generarTicket());
  };
})();
