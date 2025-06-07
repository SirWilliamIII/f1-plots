document.addEventListener("DOMContentLoaded", function () {
  // Elements
  var yearSelect = document.getElementById("year");
  var sessionSelect = document.getElementById("session");
  var raceSelect = document.getElementById("race");
  var form2Container = document.getElementById("form2-container");
  var activateForm2Button = document.getElementById("getYear");
  var hiddenYear = document.getElementById("hidden-year");
  var hiddenSession = document.getElementById("hidden-session");
  var form2 = document.getElementById("form2");
  var driverSelectContainer = document.getElementById(
    "driver-select-container"
  );
  var driver1Select = document.getElementById("driver1");
  var driver2Select = document.getElementById("driver2");
  var selectDriversBtn = document.getElementById("select-drivers-btn");
  var chooseDriversBtn = document.getElementById("choose-drivers-btn");

  // Loader for Choose Grand Prix button
  function finishGrandPrixLoading() {
    var text = document.getElementById("getYear-text");
    var loader = document.getElementById("getYear-loader");
    if (text && loader && activateForm2Button) {
      text.style.display = "inline";
      loader.style.display = "none";
      activateForm2Button.disabled = false;
    }
  }

  // Populate and enable the driver form after Grand Prix is selected and drivers are loaded
  function showDriverForm(drivers) {
    if (driver1Select && driver2Select) {
      driver1Select.innerHTML = '<option value="">Select driver 1</option>';
      driver2Select.innerHTML = '<option value="">Select driver 2</option>';
      drivers.forEach(function (driver) {
        var opt1 = document.createElement("option");
        opt1.value = driver.abbreviation;
        opt1.textContent = driver.broadcast_name;
        driver1Select.appendChild(opt1);
        var opt2 = document.createElement("option");
        opt2.value = driver.abbreviation;
        opt2.textContent = driver.broadcast_name;
        driver2Select.appendChild(opt2);
      });
      driver1Select.disabled = false;
      driver2Select.disabled = false;
      if (selectDriversBtn) selectDriversBtn.disabled = false;
    }
    // Set hidden fields for year/session/race
    var driverYear = document.getElementById("driver-year");
    var driverSession = document.getElementById("driver-session");
    var driverRace = document.getElementById("driver-race");
    if (driverYear && yearSelect) driverYear.value = yearSelect.value;
    if (driverSession && sessionSelect)
      driverSession.value = sessionSelect.value;
    if (driverRace && raceSelect) driverRace.value = raceSelect.value;
  }

  // Update races dropdown based on year/session
  function updateRaces() {
    var year = yearSelect.value;
    var session = sessionSelect.value;
    if (year && session) {
      fetch("/get_races", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ year: year, session: session }),
      })
        .then((response) => response.json())
        .then((data) => {
          raceSelect.innerHTML = "";
          if (data.races && data.races.length > 0) {
            data.races.forEach((race) => {
              var option = document.createElement("option");
              option.value = race.event_name;
              option.textContent = race.country + " (" + race.event_name + ")";
              raceSelect.appendChild(option);
            });
            raceSelect.disabled = false;
            if (chooseDriversBtn) chooseDriversBtn.disabled = false;
          } else {
            var option = document.createElement("option");
            option.value = "";
            option.textContent = "No races found";
            raceSelect.appendChild(option);
            raceSelect.disabled = true;
            if (chooseDriversBtn) chooseDriversBtn.disabled = true;
          }
          form2Container.classList.remove("disabled");
          finishGrandPrixLoading();
        })
        .catch((error) => {
          form2Container.classList.remove("disabled");
          raceSelect.innerHTML = "";
          var option = document.createElement("option");
          option.value = "";
          option.textContent = "Error loading countries";
          raceSelect.appendChild(option);
          raceSelect.disabled = true;
          if (chooseDriversBtn) chooseDriversBtn.disabled = true;
          finishGrandPrixLoading();
        });
    }
  }

  // Before submitting form2, set hidden year/session values
  if (form2) {
    form2.addEventListener("submit", function (e) {
      e.preventDefault();
      if (hiddenYear && yearSelect) hiddenYear.value = yearSelect.value;
      if (hiddenSession && sessionSelect)
        hiddenSession.value = sessionSelect.value;

      // Simulate fetching drivers for the selected race
      var dummyDrivers = window.driverOptions || [];
      if (dummyDrivers.length === 0) {
        // fallback: show a message or keep disabled
        return;
      }
      showDriverForm(dummyDrivers);
      driverSelectContainer.classList.remove("disabled");

      // Loader for Choose Drivers (Select Grand Prix form)
      var chooseDriversBtnText = document.getElementById(
        "choose-drivers-btn-text"
      );
      var chooseDriversLoader = document.getElementById(
        "choose-drivers-loader"
      );
      if (chooseDriversBtnText && chooseDriversLoader) {
        chooseDriversBtnText.style.display = "none";
        chooseDriversLoader.style.display = "inline-block";
      }
    });
  }

  // Helper to switch forms
  function showForm(formIdToShow) {
    const forms = [
      document.getElementById("form1-container"),
      document.getElementById("form2-container"),
      document.getElementById("driver-select-container"),
    ];
    forms.forEach((form) => {
      if (form) {
        if (form.id === formIdToShow) {
          form.classList.add("active-form");
          form.classList.remove("fade");
        } else {
          form.classList.remove("active-form");
          form.classList.add("fade");
        }
      }
    });
  }

  // On page load, show only the first form
  showForm("form1-container");

  // Choose Grand Prix button spinner logic
  if (activateForm2Button) {
    activateForm2Button.addEventListener("click", function () {
      var text = document.getElementById("getYear-text");
      var loader = document.getElementById("getYear-loader");
      if (text && loader) {
        text.style.display = "none";
        loader.style.display = "inline-block";
      }
      activateForm2Button.disabled = true;
      updateRaces();
      showForm("form2-container");
    });
  }

  // Loader for Generate Plots (driver selection form)
  var driverForm = document.getElementById("driver-select-form");
  if (driverForm) {
    driverForm.addEventListener("submit", function () {
      var btnText = document.getElementById("select-drivers-btn-text");
      var btnLoader = document.getElementById("select-drivers-loader");
      if (btnText && btnLoader) {
        btnText.style.display = "none";
        btnLoader.style.display = "inline-block";
      }
    });

    // Populate driver form on load if driverOptions are available
    if (window.driverOptions && window.driverOptions.length > 0) {
      showDriverForm(window.driverOptions);
    }
  }

  // Add this handler for the Choose Drivers button (form2)
  if (chooseDriversBtn) {
    chooseDriversBtn.addEventListener("click", function (e) {
      e.preventDefault();

      // Show loader
      var chooseDriversBtnText = document.getElementById(
        "choose-drivers-btn-text"
      );
      var chooseDriversLoader = document.getElementById(
        "choose-drivers-loader"
      );
      if (chooseDriversBtnText && chooseDriversLoader) {
        chooseDriversBtnText.style.display = "none";
        chooseDriversLoader.style.display = "inline-block";
      }

      // Gather selected values
      var year = yearSelect ? yearSelect.value : "";
      var race = raceSelect ? raceSelect.value : "";
      var session = sessionSelect ? sessionSelect.value : "";

      // Fetch drivers from backend
      fetch("/get_drivers", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ year: year, race: race, session: session }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.drivers && data.drivers.length > 0) {
            showDriverForm(data.drivers);
          } else {
            alert("No drivers found for this session.");
          }
          // Hide loader
          if (chooseDriversBtnText && chooseDriversLoader) {
            chooseDriversBtnText.style.display = "inline";
            chooseDriversLoader.style.display = "none";
          }
          // Always show the third form
          showForm("driver-select-container");
        })
        .catch((error) => {
          alert("Error fetching drivers.");
          if (chooseDriversBtnText && chooseDriversLoader) {
            chooseDriversBtnText.style.display = "inline";
            chooseDriversLoader.style.display = "none";
          }
        });
    });
  }
});
