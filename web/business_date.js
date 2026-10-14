(function (root) {
  "use strict";

  root.FlowERPBusinessDate = {
    fromSetup: function (payload) {
      const value = payload && payload.business_date;
      if (typeof value !== "string" || value.length !== 10 || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
      const year = Number(value.slice(0, 4));
      const month = Number(value.slice(5, 7));
      const day = Number(value.slice(8, 10));
      if (year < 1 || month < 1 || month > 12 || day < 1) return "";
      const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
      const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
      return day <= days[month - 1] ? value : "";
    }
  };
})(globalThis);
