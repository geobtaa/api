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

<style>

        .run-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
            transition: transform 0.2s;
        }

        .run-btn:hover {
            transform: scale(1.05);
        }

        .run-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .output-area {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 4px;
            margin-top: 10px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            display: none;
        }

        .output-area.visible {
            display: block;
        }

        .loading {
            color: #667eea;
            font-style: italic;
        }

        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: #2d3748;
            color: white;
            border: 1px solid #4a5568;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
            z-index: 10;
        }

        .copy-btn:hover {
            background: #4a5568;
        }

        .copy-btn:active {
            transform: scale(0.95);
        }

        pre {
            position: relative;
        }

        /* Tutorial slide wrapper - keeps content within site layout */
        .tutorial-slide-wrapper {
            margin: 2rem 0;
            padding: 2rem;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        /* Slide styles */
        #slide-container {
            position: relative;
            min-height: 600px;
            padding: 2rem 0;
        }

        .slide {
            display: none;
        }

        .slide.active {
            display: block;
            animation: fadeIn 0.3s;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
            }

            to {
                opacity: 1;
            }
        }

        /* Controls */
        .controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            margin: 30px 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }

        .controls button {
            background: white;
            color: #667eea;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }

        .controls button:hover:not(:disabled) {
            background: #f7fafc;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }

        .controls button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        #fullscreenBtn {
            font-size: 20px;
            padding: 8px 16px;
        }

        #slide-indicator {
            color: white;
            font-weight: 600;
            min-width: 120px;
            text-align: center;
        }

        /* Fullscreen styles - hide site header/footer only in fullscreen */
        html:fullscreen body.tutorial-fullscreen {
            background: #1a202c;
        }

        html:fullscreen body.tutorial-fullscreen .md-header,
        html:fullscreen body.tutorial-fullscreen .md-tabs,
        html:fullscreen body.tutorial-fullscreen .md-footer {
            display: none !important;
        }

        html:fullscreen body.tutorial-fullscreen .md-main {
            margin-top: 0 !important;
        }

        html:fullscreen body.tutorial-fullscreen .md-main__inner {
            max-width: 100%;
            padding: 40px;
            margin-top: 0;
        }

        html:fullscreen body.tutorial-fullscreen .tutorial-slide-wrapper {
            margin: 0;
            padding: 40px;
            box-shadow: none;
            border-radius: 0;
            background: #1a202c;
            color: #fff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        html:fullscreen body.tutorial-fullscreen .slide {
            font-size: 1.1em;
            color: #fff;
        }

        html:fullscreen body.tutorial-fullscreen .slide h2,
        html:fullscreen body.tutorial-fullscreen .slide h3 {
            color: #fff;
        }

        html:fullscreen body.tutorial-fullscreen .controls {
            margin-top: auto;
        }

        /* Slide heading styles to match presentation */
        .slide h2 {
            color: #005E8E;
            border-bottom: 2px solid #005E8E;
            padding-bottom: 0.5rem;
            margin-top: 0;
        }

        .slide h3 {
            color: #772424;
            margin-top: 1.5rem;
        }

        html:fullscreen body.tutorial-fullscreen .example-block {
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.2);
        }



        /* Tab Styles */
        .tabs {
            display: flex;
            margin-bottom: 0;
            background: #2d3748;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            overflow: hidden;
            margin-top: 20px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: #a0aec0;
            padding: 10px 20px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
            border-bottom: 2px solid transparent;
        }

        .tab-btn:hover {
            color: white;
            background: #4a5568;
        }

        .tab-btn.active {
            color: white;
            background: #4a5568;
            border-bottom: 2px solid #667eea;
        }

        .tab-content {
            display: none;
            background: #2d2d2d;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
            min-height: 200px;
        }

        .tab-content.active {
            display: block;
        }

        /* Adjust pre styling for tabs */
        .tab-content pre {
            margin: 0;
            border-radius: 0 0 8px 8px;
            border: none;
            max-height: 400px;
            overflow-y: auto;
        }

        .json-area {
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            padding: 15px;
            white-space: pre !important;
            overflow-x: auto;
        }

        /* Update output area for tab context */
        .output-area {
            margin-top: 0;
            /* Remove margin as it's inside tab now */
            background: #1e1e1e;
            color: #d4d4d4;
            /* Light text for dark background */
            /* Match tab background */
            min-height: 200px;
            /* Ensure some height even if empty */
            padding: 15px;
        }
    
</style>


    

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
            <p style="margin-top: 30px; color: #718096;">Use the navigation buttons below or arrow keys to move between examples.</p>
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
        <select id="slideSelect" onchange="jumpToSlide(this.value)"
            style="padding: 10px; border-radius: 5px; border: none; background: rgba(255,255,255,0.95); color: #4a5568; font-weight: 600; font-size: 14px; cursor: pointer; max-width: 250px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <!-- Populated by JS -->
        </select>
        <span id="slide-indicator" style="display: none;">Slide 1 of 3</span>
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
