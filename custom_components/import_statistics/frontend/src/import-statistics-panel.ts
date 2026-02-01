import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { HomeAssistant, UploadResponse } from './types';

/**
 * Import Statistics Panel - Web component for uploading and importing statistics
 */
@customElement('import-statistics-panel')
export class ImportStatisticsPanel extends LitElement {
    @property({ attribute: false }) public hass!: HomeAssistant;
    @property({ type: Boolean }) public narrow = false;

    @state() private selectedFile: File | null = null;
    @state() private uploadedFilename = '';
    @state() private uploadStatus = '';
    @state() private importStatus = '';
    @state() private isUploading = false;
    @state() private isImporting = false;

    static styles = css`
    :host {
      display: block;
      padding: 16px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .card {
      background: var(--card-background-color, #fff);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 16px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    h1 {
      margin: 0 0 16px 0;
      font-size: 24px;
      font-weight: 400;
      color: var(--primary-text-color, #212121);
    }

    h2 {
      margin: 0 0 16px 0;
      font-size: 20px;
      font-weight: 400;
      color: var(--primary-text-color, #212121);
    }

    .upload-section {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .file-input-wrapper {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    input[type="file"] {
      flex: 1;
      min-width: 200px;
      padding: 8px;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 4px;
      background: var(--primary-background-color, #fafafa);
      color: var(--primary-text-color, #212121);
    }

    button {
      padding: 10px 24px;
      border: none;
      border-radius: 4px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s;
    }

    button:hover:not(:disabled) {
      background: var(--dark-primary-color, #0288d1);
    }

    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .status {
      padding: 12px 16px;
      border-radius: 4px;
      margin-top: 12px;
      font-size: 14px;
    }

    .status.success {
      background-color: var(--success-color, #4caf50);
      color: var(--text-primary-color, #fff);
    }

    .status.error {
      background-color: var(--error-color, #f44336);
      color: var(--text-primary-color, #fff);
    }

    .info-section {
      margin: 16px 0;
    }

    .info-section p {
      margin: 8px 0;
      color: var(--secondary-text-color, #757575);
    }

    .info-section strong {
      color: var(--primary-text-color, #212121);
    }

    .info-section ul {
      margin: 8px 0;
      padding-left: 24px;
      color: var(--secondary-text-color, #757575);
    }

    .info-section li {
      margin: 4px 0;
    }

    @media (max-width: 600px) {
      :host {
        padding: 8px;
      }

      .card {
        padding: 16px;
      }

      .file-input-wrapper {
        flex-direction: column;
        align-items: stretch;
      }

      input[type="file"] {
        width: 100%;
      }

      button {
        width: 100%;
      }
    }
  `;

    render() {
        return html`
      <div class="card">
        <h1>Import Statistics - Upload File</h1>

        <div class="upload-section">
          <div class="file-input-wrapper">
            <input
              type="file"
              accept=".csv,.tsv,.txt,.json"
              @change=${this._handleFileSelect}
              ?disabled=${this.isUploading}
            />
            <button
              @click=${this._handleUpload}
              ?disabled=${this.isUploading || !this.selectedFile}
            >
              ${this.isUploading ? 'Uploading...' : 'Upload File'}
            </button>
          </div>

          ${this.uploadStatus ? html`
            <div class="status ${this.uploadStatus.startsWith('✓') ? 'success' : 'error'}">
              ${this.uploadStatus}
            </div>
          ` : ''}
        </div>
      </div>

      ${this.uploadedFilename ? html`
        <div class="card">
          <h2>Import Statistics</h2>

          <div class="info-section">
            <p>Uploaded file: <strong>${this.uploadedFilename}</strong></p>
            <p>Import settings (fixed for this version):</p>
            <ul>
              <li>Delimiter: Tab (\\t)</li>
              <li>Decimal: Dot (.)</li>
              <li>Datetime format: %d.%m.%Y %H:%M</li>
              <li>Unit from entity: true</li>
            </ul>
          </div>

          <button
            @click=${this._handleImport}
            ?disabled=${this.isImporting}
          >
            ${this.isImporting ? 'Importing...' : 'Import Statistics'}
          </button>

          ${this.importStatus ? html`
            <div class="status ${this.importStatus.startsWith('✓') ? 'success' : 'error'}">
              ${this.importStatus}
            </div>
          ` : ''}
        </div>
      ` : ''}
    `;
    }

    private _handleFileSelect(e: Event) {
        const input = e.target as HTMLInputElement;
        this.selectedFile = input.files?.[0] || null;
        this.uploadStatus = '';
        this.uploadedFilename = '';
        this.importStatus = '';
    }

    private async _handleUpload() {
        if (!this.selectedFile) {
            return;
        }

        this.isUploading = true;
        this.uploadStatus = '';
        this.importStatus = '';

        try {
            const formData = new FormData();
            formData.append('file', this.selectedFile);

            const response = await fetch('/api/import_statistics/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result: UploadResponse = await response.json();

            if (result.success && result.filename) {
                this.uploadedFilename = result.filename;
                this.uploadStatus = `✓ File uploaded successfully: ${result.filename}`;
            } else {
                this.uploadStatus = `✗ Upload failed: ${result.error || 'Unknown error'}`;
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            this.uploadStatus = `✗ Upload failed: ${errorMessage}`;
        } finally {
            this.isUploading = false;
        }
    }

    private async _handleImport() {
        if (!this.uploadedFilename) {
            return;
        }

        this.isImporting = true;
        this.importStatus = '';

        try {
            await this.hass.callService(
                'import_statistics',
                'import_from_file',
                {
                    filename: this.uploadedFilename,
                    delimiter: '\\t',
                    decimal: '.',
                    datetime_format: '%d.%m.%Y %H:%M',
                    unit_from_entity: true,
                }
            );

            this.importStatus = '✓ Import completed successfully';
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            this.importStatus = `✗ Import failed: ${errorMessage}`;
        } finally {
            this.isImporting = false;
        }
    }
}

declare global {
    interface HTMLElementTagNameMap {
        'import-statistics-panel': ImportStatisticsPanel;
    }
}
