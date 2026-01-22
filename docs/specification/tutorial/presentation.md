<style>
/* Tutorial slide wrapper - keeps content within site layout */
.tutorial-slide-wrapper {
    margin: 2rem 0;
    padding: 2rem;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Slideshow Styles for Tutorial */
#slide-container {
    min-height: 400px;
    padding: 2rem 0;
}

.slide {
    display: none;
    width: 100%;
    animation: fadeIn 0.5s;
}

.slide.active {
    display: block;
}

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
    font-size: 1.2em;
    color: #fff;
}

html:fullscreen body.tutorial-fullscreen .slide h2,
html:fullscreen body.tutorial-fullscreen .slide h3 {
    color: #fff;
    border-bottom-color: rgba(255, 255, 255, 0.3);
}

html:fullscreen body.tutorial-fullscreen .controls {
    margin-top: auto;
}
</style>

<div class="tutorial-slide-wrapper">
<div id="slide-container">
    <div class="slide active">
        <h2>1. Introduction</h2>
        <h3>What is the BTAA Geoportal API?</h3>
        <p>The API powers the BTAA Geoportal frontend and provides external access to our digital collection of
            geospatial resources. It allows for automation, integration into GIS software (like QGIS), and bulk
            data
            analysis.</p>

        <h3>Core Concepts</h3>
        <ul>
            <li><strong>RESTful Design:</strong> Standard HTTP methods (GET).</li>
            <li><strong>JSON:API Standard:</strong> Responses are structured with <code>data</code>,
                <code>attributes</code>, <code>meta</code>, and <code>links</code>.
            </li>
            <li><strong>Base URL:</strong> <code>https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/</code>
            </li>
        </ul>
    </div>

    <div class="slide">
        <h2>2. The Search Endpoint</h2>
        <p>The primary entry point for discovery is <code>/search</code>.</p>

        <h3>Key Parameters</h3>
        <ul>
            <li><code>q</code>: The main keyword search parameter (e.g., <code>?q=seattle</code>).</li>
            <li><code>include_filters</code>: Target specific fields (e.g.,
                <code>include_filters[gbl_resourceClass_sm][]=Maps</code>).
            </li>
            <li><code>page</code> &amp; <code>per_page</code>: Control pagination.</li>
            <li><code>sort</code>: Order results (e.g., <code>year_asc</code>, <code>relevance</code>).</li>
        </ul>
    </div>

    <div class="slide">
        <h2>3. Anatomy of a Response</h2>
        <p>The API follows the JSON:API specification. Here is a breakdown of the key top-level sections you
            will
            see in a search response:</p>

        <h3>jsonapi</h3>
        <p>This object describes the version of the JSON:API specification the server implements. It ensures
            clients
            know how to parse the document structure reliably.</p>

        <h3>links</h3>
        <p>These are your navigation aids. They provide pre-built URLs for:</p>
        <ul>
            <li><code>self</code>: The current request.</li>
            <li><code>next</code> / <code>prev</code>: Pagination links to traverse the result set.</li>
            <li><code>first</code> / <code>last</code>: Jumping to the beginning or end of results.</li>
        </ul>

        <h3>meta</h3>
        <p>This section contains high-level metadata about your query, such as:</p>
        <ul>
            <li><code>totalCount</code>: The total number of matching records.</li>
            <li><code>pages</code>: Total pages available.</li>
        </ul>

        <h3>data</h3>
        <p>The core array of resource objects. Each item contains:</p>
        <ul>
            <li><strong>attributes:</strong> The metadata record following the <a
                    href="https://github.com/OpenGeoMetadata/aardvark" target="_blank">OpenGeoMetadata
                    Aardvark</a>
                schema.</li>
            <li><strong>meta:</strong> Additional UI helpers, such as thumbnail URLs and generated citations.
            </li>
        </ul>

        <h3>included</h3>
        <p>This section contains "side-loaded" data. In our search context, this is where
            <strong>facets</strong>
            and aggregations live (e.g., counts of maps by provider or year).
        </p>
    </div>

    <div class="slide">
        <h2>4. The Resource Endpoint</h2>
        <p>To get full details on a single item, use <code>/resources/{id}</code>.</p>

        <h3>Anatomy of a Resource</h3>
        <pre><code>{
  "data": {
    "type": "resource",
    "id": "p16022coll205:660",
    "attributes": {
      "dct_title_s": "Guide map of Seattle",
      "dct_issued_s": "1924",
      "locn_geometry": "POLYGON((-122...))",
      "dct_references_s": "{...}" 
    }
  }
}</code></pre>
        <p><strong>Tip:</strong> The <code>dct_references_s</code> attribute contains critical links to
            downloads
            and IIIF manifests.</p>
    </div>

    <div class="slide">
        <h2>5. Practical Application</h2>
        <p>We have prepared 11 practical "recipes" or examples to demonstrate common tasks, from basic searching
            to
            extracting IIIF manifests for map viewers.</p>
        <a href="../examples" class="md-button">View Code Examples</a>
    </div>
</div>

<div class="controls">
    <button id="prevBtn" onclick="changeSlide(-1)" disabled>&larr; Previous</button>
    <select id="slideSelect" onchange="jumpToSlide(this.value)"
        style="padding: 10px; border-radius: 5px; border: none; background: rgba(255,255,255,0.95); color: #4a5568; font-weight: 600; font-size: 14px; cursor: pointer; max-width: 250px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <!-- Populated by JS -->
    </select>
    <span id="slide-indicator" style="display: none;">Slide 1 of 5</span>
    <button id="nextBtn" onclick="changeSlide(1)">Next &rarr;</button>
    <button id="fullscreenBtn" onclick="toggleFullscreen()" title="Toggle Fullscreen">&#99798;</button>
</div>
</div>

<script>
    // Slide navigation
    let currentSlide = 0;
    const slides = document.querySelectorAll('.slide');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const slideSelect = document.getElementById('slideSelect');

    // Populate Dropdown
    slides.forEach((slide, index) => {
        let title = `Slide ${index + 1}`;
        const h2 = slide.querySelector('h2');

        if (h2) title = h2.textContent;

        const option = document.createElement('option');
        option.value = index;
        option.textContent = title;
        slideSelect.appendChild(option);
    });

    function showSlide(n) {
        slides[currentSlide].classList.remove('active');
        currentSlide = (n + slides.length) % slides.length;
        slides[currentSlide].classList.add('active');

        // Update controls
        prevBtn.disabled = currentSlide === 0;
        nextBtn.disabled = currentSlide === slides.length - 1;
        slideSelect.value = currentSlide;

        // Update URL hash
        window.location.hash = 'slide-' + (currentSlide + 1);
    }

    // Initialize state from URL hash
    window.addEventListener('load', () => {
        const hash = window.location.hash;
        if (hash && hash.startsWith('#slide-')) {
            const index = parseInt(hash.replace('#slide-', '')) - 1;
            if (index >= 0 && index < slides.length) {
                showSlide(index);
            }
        } else {
            showSlide(0);
        }
    });

    function changeSlide(n) {
        const newIndex = currentSlide + n;
        if (newIndex >= 0 && newIndex < slides.length) {
            showSlide(newIndex);
        }
    }

    function jumpToSlide(index) {
        showSlide(parseInt(index));
    }

    // Fullscreen Toggle
    function toggleFullscreen() {
        const wrapper = document.querySelector('.tutorial-slide-wrapper');
        if (!document.fullscreenElement) {
            // Add class to body to indicate tutorial fullscreen mode
            document.body.classList.add('tutorial-fullscreen');
            document.documentElement.requestFullscreen().catch(err => {
                document.body.classList.remove('tutorial-fullscreen');
                console.log(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
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

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') changeSlide(-1);
        if (e.key === 'ArrowRight') changeSlide(1);
        if (e.key === 'Escape' && document.fullscreenElement) {
            document.exitFullscreen();
        }
    });
</script>
