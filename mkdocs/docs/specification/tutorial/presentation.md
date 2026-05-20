---
hide:
    - toc
---

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
            <li><strong>Base URL:</strong> <code>https://lib-geoportal-prd-web-01.oit.umn.edu/api/v1/</code>
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
    <select id="slideSelect" class="slide-select" onchange="jumpToSlide(this.value)">
        <!-- Populated by JS -->
    </select>
    <span id="slide-indicator" class="slide-indicator-hidden">Slide 1 of 5</span>
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
