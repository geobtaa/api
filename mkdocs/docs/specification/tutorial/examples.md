---
hide:
    - toc
---



<meta charset="UTF-8">
<link rel="stylesheet" href="https://pyscript.net/releases/2024.1.1/core.css">
<script type="module" src="https://pyscript.net/releases/2024.1.1/core.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>

<py-config>
packages = ["requests", "pyodide-http"]
</py-config>


    

<div class="tutorial-slide-wrapper">
    <div id="slide-container">
        <div class="slide active">
                                <div class="example-header">
                        <h3>Introduction</h3>
                        <span class="badge">Search</span>
                    </div>
            <p>11 Recipes for Success with the BTAA Geoportal API</p>
            <p>Download the full runnable Python script containing all these examples, or run them directly in your browser below!</p>
            <p><a href="../btaa_api_examples.py" class="btn" download>Download Python Script</a></p>
            <p class="tutorial-intro-note">Use the navigation buttons below or arrow keys to move between examples.</p>
        </div>

        <div class="slide">
{% include "includes/examples/example-1-simple-search.html" %}
        </div>
        
        <div class="slide">
{% include "includes/examples/example-2-obtain-resource.html" %}
        </div>
        
        <div class="slide">
{% include "includes/examples/example-3-boolean-search.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-4-field-directed-search.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-5-faceted-search.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-6-faceted-search-includes.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-7-faceted-search-excludes.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-8-spatial-bbox.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-9-spatial-distance.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-10-spatial-polygon.html" %}
        </div>

        <div class="slide">
{% include "includes/examples/example-11-advanced-search.html" %}
        </div>
    </div>

    <div class="controls">
        <button id="prevBtn" onclick="changeSlide(-1)">&larr; Previous</button>
        <select id="slideSelect" class="slide-select" onchange="jumpToSlide(this.value)">
            <!-- Populated by JS -->
        </select>
        <span id="slide-indicator" class="slide-indicator-hidden">Slide 1 of 3</span>
        <button id="nextBtn" onclick="changeSlide(1)">Next &rarr;</button>
        <button id="fullscreenBtn" onclick="toggleFullscreen()" title="Toggle Fullscreen">&#99798;</button>
    </div>
</div>

<script>
        function copyCode(codeId) {
            const codeElement = document.getElementById(codeId);
            const text = codeElement.textContent;

            navigator.clipboard.writeText(text).then(() => {
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = '\u2713 Copied!';
                btn.style.background = '#48bb78';

                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '#2d3748';
                }, 2000);
            });
        }

        // Slide navigation - initialize when DOM is ready
        let currentSlide = 0;
        let slides, prevBtn, nextBtn, slideSelect;

        function initSlides() {
            slides = document.querySelectorAll('.slide');
            prevBtn = document.getElementById('prevBtn');
            nextBtn = document.getElementById('nextBtn');
            slideSelect = document.getElementById('slideSelect');

            if (!slides.length || !prevBtn || !nextBtn || !slideSelect) {
                console.error('Slide elements not found');
                return;
            }

            // Populate Dropdown
            slides.forEach((slide, index) => {
                let title = `Slide ${index + 1}`;
                const h2 = slide.querySelector('h2');
                const h3 = slide.querySelector('h3');

                if (h3) title = h3.textContent;
                else if (h2) title = h2.textContent;

                // Clean up title
                title = title.replace(/^\d+\.\s*/, ''); // Remove numbering if present to be cleaner
                if (index > 0) title = `${index}. ${title}`; // Add our own numbering for examples

                const option = document.createElement('option');
                option.value = index;
                option.textContent = title;
                slideSelect.appendChild(option);
            });

            // Initialize state from URL hash
            const hash = window.location.hash;
            if (hash && hash.startsWith('#slide-')) {
                const index = parseInt(hash.replace('#slide-', '')) - 1;
                if (index >= 0 && index < slides.length) {
                    showSlide(index);
                } else {
                    showSlide(0);
                }
            } else {
                showSlide(0);
            }
        }

        function showSlide(n) {
            if (!slides || slides.length === 0) return;
            
            slides[currentSlide].classList.remove('active');
            currentSlide = (n + slides.length) % slides.length;
            slides[currentSlide].classList.add('active');

            // Update controls
            if (prevBtn) prevBtn.disabled = currentSlide === 0;
            if (nextBtn) nextBtn.disabled = currentSlide === slides.length - 1;
            if (slideSelect) slideSelect.value = currentSlide;

            // Update URL hash
            window.location.hash = 'slide-' + (currentSlide + 1);
        }

        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initSlides);
        } else {
            // DOM is already ready
            initSlides();
        }

        function changeSlide(n) {
            const newIndex = currentSlide + n;
            if (newIndex >= 0 && newIndex < slides.length) {
                showSlide(newIndex);
            }
        }

        function jumpToSlide(index) {
            showSlide(parseInt(index));
        }

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') changeSlide(-1);
            if (e.key === 'ArrowRight') changeSlide(1);
            if (e.key === 'Escape' && document.fullscreenElement) {
                document.exitFullscreen();
            }
        });

        // Fullscreen functionality
        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                // Add class to body to indicate tutorial fullscreen mode
                document.body.classList.add('tutorial-fullscreen');
                document.documentElement.requestFullscreen().catch(err => {
                    document.body.classList.remove('tutorial-fullscreen');
                    console.log(`Error attempting to enable fullscreen: ${err.message}`);
                });
            } else {
                document.body.classList.remove('tutorial-fullscreen');
                document.exitFullscreen();
            }
        }

        // Remove class when exiting fullscreen via ESC key
        document.addEventListener('fullscreenchange', () => {
            if (!document.fullscreenElement) {
                document.body.classList.remove('tutorial-fullscreen');
            }
        });
        // Tab switching
        function openTab(evt, tabId) {
            // Find the parent example-block to scope the tab switching (optional, but good for safety)
            // But simply: hide all tab-content in the immediate container, remove active from buttons

            // Get the button that was clicked
            var btn = evt.currentTarget;
            var container = btn.closest('.example-block');

            // Hide all tab content in this container
            var tabContents = container.getElementsByClassName("tab-content");
            for (var i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove("active");
            }

            // Remove active class from all buttons in this container
            var tabBtns = container.getElementsByClassName("tab-btn");
            for (var i = 0; i < tabBtns.length; i++) {
                tabBtns[i].classList.remove("active");
            }

            // Show the current tab, and add an "active" class to the button that opened the tab
            document.getElementById(tabId).classList.add("active");
            btn.classList.add("active");
        }
</script>
