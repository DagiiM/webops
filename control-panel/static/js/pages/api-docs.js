/* Moved from templates/api/docs.html (ui-skill rule 17: no inline <script>). */
'use strict';

class APIDocumentation {
    constructor() {
        this.apiData = null;
        this.loadDocumentation();
    }

    async loadDocumentation() {
        try {
            const response = await fetch('/api/docs/data/');
            this.apiData = await response.json();
            this.renderNavigation();
            this.renderEndpoints();
        } catch (error) {
            console.error('Failed to load API documentation:', error);
            WebOps.Toast.error('Failed to load API documentation');
        }
    }

    renderNavigation() {
        const nav = document.getElementById('docsNav');
        const groups = this.apiData.endpoints;

        Object.entries(groups).forEach(([groupName, endpoints]) => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'docs-nav-group';

            const title = document.createElement('div');
            title.className = 'docs-nav-title';
            title.textContent = groupName;
            groupDiv.appendChild(title);

            endpoints.forEach(endpoint => {
                const item = document.createElement('div');
                item.className = 'docs-nav-item';
                item.textContent = `${endpoint.method} ${endpoint.path.split('/').pop() || 'root'}`;
                item.dataset.section = `${endpoint.method}-${endpoint.path}`;
                item.onclick = () => this.scrollToEndpoint(item.dataset.section);
                groupDiv.appendChild(item);
            });

            nav.appendChild(groupDiv);
        });
    }

    renderEndpoints() {
        const container = document.getElementById('endpointsContainer');
        const groups = this.apiData.endpoints;

        Object.entries(groups).forEach(([groupName, endpoints]) => {
            endpoints.forEach(endpoint => {
                const card = this.createEndpointCard(endpoint);
                container.appendChild(card);
            });
        });
    }

    createEndpointCard(endpoint) {
        const card = document.createElement('section');
        card.className = 'webops-endpoint-card';
        card.id = `${endpoint.method}-${endpoint.path}`;

        const header = document.createElement('div');
        header.className = 'webops-endpoint-header';

        const methodBadge = document.createElement('span');
        methodBadge.className = `webops-method-badge webops-method-badge--${endpoint.method.toLowerCase()}`;
        methodBadge.textContent = endpoint.method;

        const path = document.createElement('code');
        path.className = 'webops-endpoint-path';
        path.textContent = endpoint.path;

        header.appendChild(methodBadge);
        header.appendChild(path);

        if (endpoint.authentication_required) {
            const authBadge = document.createElement('span');
            authBadge.className = 'webops-auth-badge';
            authBadge.innerHTML = '&#128274; Auth Required';
            header.appendChild(authBadge);
        }

        const description = document.createElement('p');
        description.className = 'webops-endpoint-description';
        description.textContent = endpoint.description;

        card.appendChild(header);
        card.appendChild(description);

        if (endpoint.parameters && endpoint.parameters.length > 0) {
            card.appendChild(this.createParametersSection(endpoint.parameters));
        }

        if (endpoint.request_body) {
            card.appendChild(this.createRequestBodySection(endpoint.request_body));
        }

        if (endpoint.examples && endpoint.examples.length > 0) {
            card.appendChild(this.createExamplesSection(endpoint.examples, endpoint));
        }

        if (endpoint.error_responses && endpoint.error_responses.length > 0) {
            card.appendChild(this.createErrorsSection(endpoint.error_responses));
        }

        return card;
    }

    createParametersSection(parameters) {
        const section = document.createElement('div');

        const title = document.createElement('h3');
        title.className = 'webops-section-title';
        title.textContent = 'Parameters';
        section.appendChild(title);

        const table = document.createElement('table');
        table.className = 'webops-param-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>In</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                ${parameters.map(param => `
                    <tr>
                        <td>
                            <code>${param.name}</code>
                            ${param.required ? '<span class="webops-required-badge">Required</span>' : ''}
                        </td>
                        <td><code>${param.type}</code></td>
                        <td>${param.in}</td>
                        <td>${param.description || ''}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        section.appendChild(table);

        return section;
    }

    createRequestBodySection(requestBody) {
        const section = document.createElement('div');

        const title = document.createElement('h3');
        title.className = 'webops-section-title';
        title.textContent = 'Request Body';
        section.appendChild(title);

        const table = document.createElement('table');
        table.className = 'webops-param-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Field</th>
                    <th>Type</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                ${Object.entries(requestBody).map(([key, field]) => `
                    <tr>
                        <td>
                            <code>${key}</code>
                            ${field.required ? '<span class="webops-required-badge">Required</span>' : ''}
                        </td>
                        <td><code>${field.type}</code></td>
                        <td>${field.description || ''}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        section.appendChild(table);

        return section;
    }

    createExamplesSection(examples, endpoint) {
        const section = document.createElement('div');

        const title = document.createElement('h3');
        title.className = 'webops-section-title';
        title.textContent = 'Examples';
        section.appendChild(title);

        const tabs = document.createElement('div');
        tabs.className = 'webops-tabs';

        const curlTab = document.createElement('div');
        curlTab.className = 'webops-tab webops-tab--active';
        curlTab.textContent = 'cURL';
        curlTab.onclick = () => this.switchTab(curlTab, 'curl');

        const jsTab = document.createElement('div');
        jsTab.className = 'webops-tab';
        jsTab.textContent = 'JavaScript';
        jsTab.onclick = () => this.switchTab(jsTab, 'javascript');

        const pythonTab = document.createElement('div');
        pythonTab.className = 'webops-tab';
        pythonTab.textContent = 'Python';
        pythonTab.onclick = () => this.switchTab(pythonTab, 'python');

        tabs.appendChild(curlTab);
        tabs.appendChild(jsTab);
        tabs.appendChild(pythonTab);
        section.appendChild(tabs);

        examples.forEach((example, idx) => {
            if (idx > 0) return; // Only show first example

            const curlContent = this.createCodeBlock(
                this.generateCurlExample(example),
                'curl',
                true
            );

            const jsContent = this.createCodeBlock(
                this.generateJavaScriptExample(example),
                'javascript'
            );

            const pythonContent = this.createCodeBlock(
                this.generatePythonExample(example),
                'python'
            );

            section.appendChild(curlContent);
            section.appendChild(jsContent);
            section.appendChild(pythonContent);
        });

        return section;
    }

    createErrorsSection(errors) {
        const section = document.createElement('div');

        const title = document.createElement('h3');
        title.className = 'webops-section-title';
        title.textContent = 'Error Responses';
        section.appendChild(title);

        errors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.style.marginBottom = 'var(--webops-space-3)';

            errorDiv.innerHTML = `
                <div class="webops-s-1dd87e7">
                    <span class="webops-method-badge webops-method-badge--delete">${error.status}</span>
                    <strong class="webops-s-62105ae">${error.title}</strong>
                </div>
                <p class="webops-s-773ba08">${error.description}</p>
                ${this.createCodeBlock(JSON.stringify(error.example, null, 2)).outerHTML}
            `;

            section.appendChild(errorDiv);
        });

        return section;
    }

    createCodeBlock(code, language = '', active = true) {
        const div = document.createElement('div');
        div.className = `webops-tab-content ${active ? 'webops-tab-content--active' : ''}`;
        div.dataset.lang = language;

        const codeBlock = document.createElement('div');
        codeBlock.className = 'webops-code-block';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'webops-copy-button';
        copyBtn.textContent = 'Copy';
        copyBtn.onclick = () => this.copyCode(code);

        const pre = document.createElement('pre');
        pre.textContent = code;

        codeBlock.appendChild(copyBtn);
        codeBlock.appendChild(pre);
        div.appendChild(codeBlock);

        return div;
    }

    generateCurlExample(example) {
        const req = example.request;
        let curl = `curl -X ${req.method} \\\n  '${window.location.origin}${req.url}'`;

        if (req.headers) {
            Object.entries(req.headers).forEach(([key, value]) => {
                curl += ` \\\n  -H '${key}: ${value}'`;
            });
        }

        if (req.body) {
            curl += ` \\\n  -d '${JSON.stringify(req.body, null, 2)}'`;
        }

        return curl;
    }

    generateJavaScriptExample(example) {
        const req = example.request;
        let js = `const response = await fetch('${req.url}', {\n`;
        js += `  method: '${req.method}',\n`;
        js += `  headers: ${JSON.stringify(req.headers, null, 4)},\n`;
        if (req.body) {
            js += `  body: JSON.stringify(${JSON.stringify(req.body, null, 4)})\n`;
        }
        js += `});\n\nconst data = await response.json();\nconsole.log(data);`;
        return js;
    }

    generatePythonExample(example) {
        const req = example.request;
        let py = `import requests\n\n`;
        py += `headers = ${JSON.stringify(req.headers, null, 4).replace(/"/g, "'")}\n\n`;
        if (req.body) {
            py += `data = ${JSON.stringify(req.body, null, 4).replace(/"/g, "'")}\n\n`;
        }
        py += `response = requests.${req.method.toLowerCase()}(\n`;
        py += `    '${window.location.origin}${req.url}',\n`;
        py += `    headers=headers`;
        if (req.body) {
            py += `,\n    json=data`;
        }
        py += `\n)\n\nprint(response.json())`;
        return py;
    }

    switchTab(tabElement, language) {
        const parent = tabElement.parentElement.parentElement;
        const tabs = parent.querySelectorAll('.webops-tab');
        const contents = parent.querySelectorAll('.webops-tab-content');

        tabs.forEach(t => t.classList.remove('webops-tab--active'));
        contents.forEach(c => c.classList.remove('webops-tab-content--active'));

        tabElement.classList.add('webops-tab--active');
        parent.querySelector(`.webops-tab-content[data-lang="${language}"]`).classList.add('webops-tab-content--active');
    }

    copyCode(code) {
        navigator.clipboard.writeText(code).then(() => {
            WebOps.Toast.success('Copied to clipboard');
        }).catch(() => {
            WebOps.Toast.error('Failed to copy');
        });
    }

    scrollToEndpoint(sectionId) {
        const element = document.getElementById(sectionId);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });

            // Update active nav item
            document.querySelectorAll('.webops-docs-nav-item').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector(`[data-section="${sectionId}"]`).classList.add('active');
        }
    }
}

function copyCode(button) {
    const code = button.nextElementSibling.textContent;
    navigator.clipboard.writeText(code).then(() => {
        button.textContent = 'Copied!';
        setTimeout(() => button.textContent = 'Copy', 2000);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    new APIDocumentation();
});
