(function () {
  function printTicket() {
    window.print();
  }
  window.printTicketThermal = printTicket;
  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("printBtn");
    if (btn) btn.addEventListener("click", printTicket);
  });
})();
