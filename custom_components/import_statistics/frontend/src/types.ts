/**
 * Type definitions for Import Statistics frontend panel
 */

/**
 * Response from the upload endpoint
 */
export interface UploadResponse {
    success: boolean;
    filename?: string;
    size?: number;
    message?: string;
    error?: string;
}

/**
 * Response from the import service
 */
export interface ImportResponse {
    success: boolean;
    message?: string;
    error?: string;
}

/**
 * Home Assistant object interface (minimal)
 */
export interface HomeAssistant {
    callService(domain: string, service: string, data?: Record<string, unknown>): Promise<void>;
}
