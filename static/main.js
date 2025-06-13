console.log("🎯 F1 Multi-Step Form Loading");

document.addEventListener("DOMContentLoaded", function() {
    console.log("🎯 DOM Loaded - Initializing Multi-Step Form");
    
    // Get all step contents
    const step1Content = document.getElementById('step1-content');
    const step2Content = document.getElementById('step2-content');
    const step3Content = document.getElementById('step3-content');
    
    // Get all buttons
    const btnToStep2 = document.getElementById('btn-to-step2');
    const btnToStep3 = document.getElementById('btn-to-step3');
    const btnGeneratePlots = document.getElementById('btn-generate-plots');
    
    // Get form elements
    const yearSelect = document.getElementById('year');
    const sessionSelect = document.getElementById('session');
    const raceSelect = document.getElementById('race');
    const driver1Select = document.getElementById('driver1');
    const driver2Select = document.getElementById('driver2');
    
    // Hidden inputs
    const hiddenYear = document.getElementById('hidden-year');
    const hiddenSession = document.getElementById('hidden-session');
    const driverYear = document.getElementById('driver-year');
    const driverSession = document.getElementById('driver-session');
    const driverRace = document.getElementById('driver-race');
    
    console.log("Elements found:", {
        step1Content: !!step1Content,
        step2Content: !!step2Content,
        step3Content: !!step3Content,
        btnToStep2: !!btnToStep2,
        btnToStep3: !!btnToStep3,
        btnGeneratePlots: !!btnGeneratePlots
    });
    
    // Function to show a specific step
    function showStep(stepNumber) {
        console.log(`🔄 Showing step ${stepNumber}`);
        
        // Hide all steps
        [step1Content, step2Content, step3Content].forEach(content => {
            if (content) {
                content.classList.add('collapsed');
            }
        });
        
        // Show the target step
        switch(stepNumber) {
            case 1:
                if (step1Content) step1Content.classList.remove('collapsed');
                break;
            case 2:
                if (step2Content) step2Content.classList.remove('collapsed');
                break;
            case 3:
                if (step3Content) step3Content.classList.remove('collapsed');
                break;
        }
    }
    
    // Function to show/hide loader
    function toggleLoader(button, textId, loaderId, show) {
        const text = document.getElementById(textId);
        const loader = document.getElementById(loaderId);
        
        if (text) text.style.display = show ? 'none' : 'inline';
        if (loader) loader.style.display = show ? 'inline-block' : 'none';
        if (button) button.disabled = show;
    }
    
    // Initialize - show only step 1
    showStep(1);
    
    // Step 1 -> Step 2 (Choose Grand Prix button)
    if (btnToStep2) {
        btnToStep2.addEventListener('click', function(e) {
            e.preventDefault();
            console.log("🚀 Step 1 button clicked!");
            
            const year = yearSelect.value;
            const session = sessionSelect.value;
            
            if (!year || !session) {
                alert("Please select both year and session");
                return;
            }
            
            console.log(`📅 Selected: Year=${year}, Session=${session}`);
            
            // Show loader
            toggleLoader(btnToStep2, 'btn-to-step2-text', 'btn-to-step2-loader', true);
            
            // Update loading message
            const loadingMsg = document.getElementById('btn-to-step2-loading-msg');
            if (loadingMsg) loadingMsg.textContent = 'Loading races...';
            
            // Fetch races
            fetch("/get_races", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: `year=${year}`
            })
            .then(response => response.json())
            .then(data => {
                console.log("🏁 Races received:", data);
                
                if (raceSelect) {
                    raceSelect.innerHTML = '<option value="">Select a country</option>';
                    
                    if (data.races && data.races.length > 0) {
                        data.races.forEach(race => {
                            const option = document.createElement("option");
                            option.value = race.event_name;
                            option.textContent = `${race.country} (${race.event_name})`;
                            raceSelect.appendChild(option);
                        });
                        raceSelect.disabled = false;
                        if (btnToStep3) btnToStep3.disabled = false;
                        
                        // Set hidden values
                        if (hiddenYear) hiddenYear.value = year;
                        if (hiddenSession) hiddenSession.value = session;
                        
                        console.log(`✅ Populated ${data.races.length} races`);
                        
                        // Unlock step 2
                        unlockStep(2);
                        
                        // Show step 2
                        showStep(2);
                        
                        // Show first load warning if needed
                        const warning = document.getElementById('first-load-warning');
                        if (warning) {
                            warning.style.display = 'block';
                            setTimeout(() => { warning.style.display = 'none'; }, 5000);
                        }
                    } else {
                        alert("No races found for the selected year");
                    }
                }
            })
            .catch(error => {
                console.error("❌ Error fetching races:", error);
                alert("Error loading races. Please try again.");
            })
            .finally(() => {
                toggleLoader(btnToStep2, 'btn-to-step2-text', 'btn-to-step2-loader', false);
            });
        });
    }
    
    // Step 2 -> Step 3 (Choose Drivers button)
    if (btnToStep3) {
        btnToStep3.addEventListener('click', function(e) {
            e.preventDefault();
            console.log("🚀 Step 2 button clicked!");
            
            const year = hiddenYear ? hiddenYear.value : yearSelect.value;
            const session = hiddenSession ? hiddenSession.value : sessionSelect.value;
            const race = raceSelect.value;
            
            if (!year || !session || !race) {
                alert("Please select a race");
                return;
            }
            
            console.log(`🏁 Selected: Year=${year}, Session=${session}, Race=${race}`);
            
            // Show loader
            toggleLoader(btnToStep3, 'btn-to-step3-text', 'btn-to-step3-loader', true);
            
            // Fetch drivers
            fetch("/get_drivers", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: `year=${year}&race=${encodeURIComponent(race)}&session=${session}`
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("🏎️ Drivers received:", data);
                
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                if (driver1Select && driver2Select) {
                    driver1Select.innerHTML = '<option value="">Select driver 1</option>';
                    driver2Select.innerHTML = '<option value="">Select driver 2</option>';
                    
                    if (data.drivers && data.drivers.length > 0) {
                        data.drivers.forEach(driver => {
                            const opt1 = document.createElement("option");
                            opt1.value = driver.abbreviation;
                            opt1.textContent = driver.broadcast_name;
                            driver1Select.appendChild(opt1);
                            
                            const opt2 = document.createElement("option");
                            opt2.value = driver.abbreviation;
                            opt2.textContent = driver.broadcast_name;
                            driver2Select.appendChild(opt2);
                        });
                        
                        driver1Select.disabled = false;
                        driver2Select.disabled = false;
                        if (btnGeneratePlots) btnGeneratePlots.disabled = false;
                        
                        // Set hidden values for final form
                        if (driverYear) driverYear.value = year;
                        if (driverSession) driverSession.value = session;
                        if (driverRace) driverRace.value = race;
                        
                        console.log(`✅ Populated ${data.drivers.length} drivers`);
                        
                        // Unlock step 3
                        unlockStep(3);
                        
                        // Show step 3
                        showStep(3);
                    } else {
                        alert("No drivers found for this session");
                    }
                } else {
                    alert("Error: Driver selection elements not found");
                }
            })
            .catch(error => {
                console.error("❌ Error fetching drivers:", error);
                alert("Error loading drivers. This session might not have data available. Please try a different race or year.");
            })
            .finally(() => {
                toggleLoader(btnToStep3, 'btn-to-step3-text', 'btn-to-step3-loader', false);
            });
        });
    }
    
    // Generate Plots form submission
    const formDrivers = document.getElementById('form-drivers');
    if (formDrivers && btnGeneratePlots) {
        formDrivers.addEventListener('submit', function(e) {
            if (!driver1Select.value || !driver2Select.value) {
                e.preventDefault();
                alert("Please select both drivers");
                return;
            }
            
            if (driver1Select.value === driver2Select.value) {
                e.preventDefault();
                alert("Please select two different drivers");
                return;
            }
            
            console.log("📊 Generating plots for:", driver1Select.value, "vs", driver2Select.value);
            toggleLoader(btnGeneratePlots, 'btn-generate-plots-text', 'btn-generate-plots-loader', true);
        });
    }
    
    // Track which steps are unlocked
    let unlockedSteps = [1]; // Start with only step 1 unlocked
    
    // Function to unlock a step
    function unlockStep(stepNumber) {
        if (!unlockedSteps.includes(stepNumber)) {
            unlockedSteps.push(stepNumber);
            const stepBox = document.getElementById(`step${stepNumber}`);
            if (stepBox) {
                stepBox.classList.remove('locked');
                stepBox.classList.add('unlocked');
            }
        }
    }
    
    // Add click handlers to step titles to expand/collapse
    document.querySelectorAll('.step-title').forEach((title, index) => {
        const stepNumber = index + 1;
        title.addEventListener('click', function(e) {
            // Check if this step is unlocked
            if (!unlockedSteps.includes(stepNumber)) {
                e.preventDefault();
                e.stopPropagation();
                return; // Don't allow clicking on locked steps
            }
            
            const targetId = this.getAttribute('data-target');
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                if (targetContent.classList.contains('collapsed')) {
                    // Collapse all others first
                    document.querySelectorAll('.step-content').forEach(content => {
                        content.classList.add('collapsed');
                    });
                    // Then expand this one
                    targetContent.classList.remove('collapsed');
                } else {
                    targetContent.classList.add('collapsed');
                }
            }
        });
    });
    
    // Initially lock steps 2 and 3
    const step2Box = document.getElementById('step2');
    const step3Box = document.getElementById('step3');
    if (step2Box) step2Box.classList.add('locked');
    if (step3Box) step3Box.classList.add('locked');
    
    console.log("🎯 Multi-Step Form initialization complete!");
});