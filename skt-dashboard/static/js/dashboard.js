const chartColors = ["#0b3d91", "#198754", "#ffc107", "#0dcaf0", "#6c757d", "#dc3545", "#18a0a8"];

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".data-table").forEach((table) => {
    new DataTable(table, {
      pageLength: 25,
      order: [],
      responsive: true
    });
  });

  if (document.getElementById("coursesBySection")) {
    loadCharts();
  }
});

async function loadCharts() {
  const response = await fetch(`/api/charts${window.location.search}`);
  const data = await response.json();

  makeChart("coursesBySection", "bar", {
    labels: data.sections,
    datasets: [{ label: "Courses", data: data.coursesBySection, backgroundColor: "#0b3d91" }]
  });

  makeChart("statusDistribution", "doughnut", {
    labels: data.statusLabels,
    datasets: [{ data: data.statusCounts, backgroundColor: chartColors }]
  });

  makeChart("coursesByMonth", "line", {
    labels: data.months,
    datasets: [
      { label: "Courses", data: data.coursesByMonth, borderColor: "#0b3d91", backgroundColor: "rgba(11,61,145,0.12)", tension: 0.3 },
      { label: "Completed", data: data.completedByMonth, borderColor: "#198754", backgroundColor: "rgba(25,135,84,0.12)", tension: 0.3 },
      { label: "Upcoming", data: data.upcomingByMonth, borderColor: "#0dcaf0", backgroundColor: "rgba(13,202,240,0.12)", tension: 0.3 }
    ]
  });

  makeChart("participantsBySection", "bar", {
    labels: data.sections,
    datasets: [
      { label: "Target", data: data.targetBySection, backgroundColor: "#0b3d91" },
      { label: "Actual", data: data.actualBySection, backgroundColor: "#198754" }
    ]
  });

  makeChart("budgetBySection", "bar", {
    labels: data.sections,
    datasets: [{ label: "Budget (RM)", data: data.budgetBySection, backgroundColor: "#18a0a8" }]
  });

  makeChart("topBudget", "bar", {
    labels: data.topBudgetLabels,
    datasets: [{ label: "Budget (RM)", data: data.topBudgetValues, backgroundColor: "#0b3d91" }]
  }, { indexAxis: "y" });

  makeChart("typeBySection", "bar", {
    labels: data.typeSectionLabels,
    datasets: data.typeSectionDatasets
  }, { scales: { x: { stacked: true }, y: { stacked: true } } });
}

function makeChart(id, type, data, extraOptions = {}) {
  const element = document.getElementById(id);
  if (!element) return;
  new Chart(element, {
    type,
    data,
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" }
      },
      scales: type === "doughnut" ? {} : {
        y: { beginAtZero: true },
        x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 0 } }
      },
      ...extraOptions
    }
  });
}
