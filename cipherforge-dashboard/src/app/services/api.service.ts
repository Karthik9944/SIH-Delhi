import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, map, retry, throwError } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  Certificate,
  DeleteResult,
  Device,
  FileMetadata,
  FileWipeRequest,
  FileShredStartRequest,
  FilesystemBrowseResponse,
  FolderWipeJobStatus,
  FolderWipeRequest,
  LogicalDriveInfo,
  Stats,
  WipeJobStatus,
  WipeStartRequest
} from '../core/models/api.models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient) {}

  getDevices(): Observable<Device[]> {
    return this.http.get<unknown>(`${this.baseUrl}/devices`).pipe(
      retry({ count: 2, delay: 500 }),
      map((response) => this.extractArray<Record<string, unknown>>(response, ['devices', 'data', 'items', 'value'])) ,
      map((devices) => devices.map((device, index) => this.normalizeDevice(device, index))),
      catchError((error) => this.handleError(error, 'fetch devices'))
    );
  }

  getWipeJobs(): Observable<WipeJobStatus[]> {
    return this.http.get<unknown>(`${this.baseUrl}/wipe/jobs`).pipe(
      retry({ count: 2, delay: 500 }),
      map((response) => this.extractArray<Record<string, unknown>>(response, ['jobs', 'data', 'items', 'value'])),
      map((jobs) => jobs.map((job) => this.normalizeWipeJob(job))),
      catchError((error) => this.handleError(error, 'fetch wipe jobs'))
    );
  }

  getDrives(): Observable<LogicalDriveInfo[]> {
    return this.http.get<unknown>(`${this.baseUrl}/drives`).pipe(
      map((response) => this.extractArray<LogicalDriveInfo>(response, ['drives', 'data', 'items'])),
      catchError((error) => this.handleError(error, 'fetch drives'))
    );
  }

  browseFilesystem(path: string): Observable<FilesystemBrowseResponse> {
    return this.http.get<unknown>(`${this.baseUrl}/filesystem`, { params: { path } }).pipe(
      map((response) => this.extractObject<Record<string, unknown>>(response, ['data', 'result'])),
      map((payload) => this.normalizeFilesystem(payload)),
      catchError((error) => this.handleError(error, 'browse filesystem'))
    );
  }

  getWipeMethods(): Observable<string[]> {
    return this.http.get<unknown>(`${this.baseUrl}/wipe/methods`).pipe(
      map((response) => this.extractArray<string>(response, ['methods', 'data', 'items'])),
      catchError((error) => this.handleError(error, 'fetch wipe methods'))
    );
  }

  startWipe(payload: WipeStartRequest): Observable<WipeJobStatus> {
    return this.http.post<unknown>(`${this.baseUrl}/wipe/start`, payload).pipe(
      map((response) => this.extractObject<Record<string, unknown>>(response, ['data', 'result', 'job'])),
      map((job) => this.normalizeWipeJob(job)),
      catchError((error) => this.handleError(error, 'start wipe job'))
    );
  }

  startFileShred(payload: FileShredStartRequest): Observable<WipeJobStatus> {
    const requestPayload: WipeStartRequest & Record<string, unknown> = {
      mode: payload.mode,
      device: payload.drive,
      method: payload.method,
      drive: payload.drive,
      targetPath: payload.targetPath
    };

    return this.startWipe(requestPayload);
  }

  wipeFile(payload: FileWipeRequest): Observable<DeleteResult> {
    return this.http.post<unknown>(`${this.baseUrl}/wipe/file`, payload).pipe(
      map((response) => this.extractObject<DeleteResult>(response, ['data', 'result'])),
      catchError((error) => this.handleError(error, 'secure delete file'))
    );
  }

  wipeFolder(payload: FolderWipeRequest): Observable<DeleteResult> {
    return this.http.post<unknown>(`${this.baseUrl}/wipe/folder`, payload).pipe(
      map((response) => this.extractObject<DeleteResult>(response, ['data', 'result'])),
      catchError((error) => this.handleError(error, 'secure delete folder'))
    );
  }

  startFolderWipe(payload: FolderWipeRequest): Observable<FolderWipeJobStatus> {
    return this.http.post<unknown>(`${this.baseUrl}/wipe/folder/start`, payload).pipe(
      map((response) => this.extractObject<FolderWipeJobStatus>(response, ['data', 'result', 'job'])),
      catchError((error) => this.handleError(error, 'start folder wipe job'))
    );
  }

  getFolderWipeStatus(jobId: string): Observable<FolderWipeJobStatus> {
    return this.http.get<unknown>(`${this.baseUrl}/wipe/folder/status/${jobId}`).pipe(
      map((response) => this.extractObject<FolderWipeJobStatus>(response, ['data', 'result', 'job', 'status'])),
      catchError((error) => this.handleError(error, `fetch folder wipe status for job ${jobId}`))
    );
  }

  getWipeStatus(jobId: string): Observable<WipeJobStatus> {
    return this.http.get<unknown>(`${this.baseUrl}/wipe/status/${jobId}`).pipe(
      map((response) => this.extractObject<Record<string, unknown>>(response, ['data', 'result', 'job', 'status'])),
      map((job) => this.normalizeWipeJob(job)),
      catchError((error) => this.handleError(error, `fetch wipe status for job ${jobId}`))
    );
  }

  getCertificates(): Observable<Certificate[]> {
    return this.http.get<unknown>(`${this.baseUrl}/certificates`).pipe(
      retry({ count: 2, delay: 500 }),
      map((response) => this.extractArray<Record<string, unknown>>(response, ['certificates', 'data', 'items', 'value'])),
      map((certificates) => certificates.map((certificate) => this.normalizeCertificate(certificate))),
      catchError((error) => this.handleError(error, 'fetch certificates'))
    );
  }

  downloadCertificatePdf(jobId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/certificate/download/${jobId}`, { responseType: 'blob' }).pipe(
      catchError((error) => this.handleError(error, `download certificate for job ${jobId}`))
    );
  }

  downloadCertificateJson(jobId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/certificate/download-json/${jobId}`, { responseType: 'blob' }).pipe(
      catchError((error) => this.handleError(error, `download certificate JSON for job ${jobId}`))
    );
  }

  getStats(): Observable<Stats> {
    return this.http.get<unknown>(`${this.baseUrl}/admin/stats`).pipe(
      retry({ count: 2, delay: 500 }),
      map((response) => this.normalizeStats(this.extractObject<Record<string, unknown>>(response, ['stats', 'data', 'result', 'value']))),
      catchError((error) => this.handleError(error, 'fetch system statistics'))
    );
  }

  private normalizeDevice(source: Record<string, unknown>, index: number): Device {
    return {
      id: this.readNumber(source, ['id']) ?? index + 1,
      deviceName: this.readString(source, ['deviceName', 'device_name', 'device']) ?? 'Unknown',
      deviceType: this.readString(source, ['deviceType', 'device_type', 'type']) ?? 'Unknown',
      size: this.readString(source, ['size']) ?? '0B',
      serialNumber: this.readString(source, ['serialNumber', 'serial_number', 'serial']) ?? 'UNKNOWN',
      lastSeenAt: this.readString(source, ['lastSeenAt', 'last_seen_at']) ?? new Date().toISOString()
    };
  }

  private normalizeWipeJob(source: Record<string, unknown>): WipeJobStatus {
    return {
      jobId: this.readString(source, ['jobId', 'job_id']) ?? '',
      engineJobId: this.readString(source, ['engineJobId', 'engine_job_id']) ?? '',
      device: this.readString(source, ['device']) ?? 'Unknown',
      wipeMethod: this.readString(source, ['wipeMethod', 'wipe_method', 'method']) ?? 'Unknown',
      status: this.readString(source, ['status']) ?? 'QUEUED',
      progress: this.readNumber(source, ['progress']) ?? 0,
      startTime: this.readString(source, ['startTime', 'start_time']),
      endTime: this.readString(source, ['endTime', 'end_time']),
      certificateId: this.readString(source, ['certificateId', 'certificate_id']),
      error: this.readString(source, ['error']),
      jobType: this.readString(source, ['jobType', 'job_type']) as 'DEVICE' | 'FILE' | undefined,
      target: this.readString(source, ['target']) ?? undefined
    };
  }

  private normalizeCertificate(source: Record<string, unknown>): Certificate {
    return {
      id: this.readString(source, ['id']) ?? '',
      jobId: this.readString(source, ['jobId', 'job_id']) ?? '',
      method: this.readString(source, ['method', 'wipe_method']) ?? 'Unknown',
      verificationStatus: this.readString(source, ['verificationStatus', 'verification_status']) ?? 'UNKNOWN',
      recoveredFiles: this.readNumber(source, ['recoveredFiles', 'recovered_files']) ?? 0,
      timestamp: this.readString(source, ['timestamp']) ?? new Date().toISOString()
    };
  }

  private normalizeFilesystem(source: Record<string, unknown>): FilesystemBrowseResponse {
    const filesRaw = Array.isArray(source['files']) ? source['files'] : [];
    const files: FileMetadata[] = filesRaw.map((item) => {
      if (typeof item === 'string') {
        return { name: item, size: '', size_bytes: 0 };
      }
      if (this.isObject(item)) {
        return {
          name: this.readString(item, ['name']) ?? 'unknown',
          size: this.readString(item, ['size']) ?? '',
          size_bytes: this.readNumber(item, ['size_bytes', 'sizeBytes']) ?? 0
        };
      }
      return { name: 'unknown', size: '', size_bytes: 0 };
    });

    return {
      path: this.readString(source, ['path']) ?? '',
      folders: this.extractArray<string>(source['folders'], []),
      files
    };
  }

  private extractArray<T>(response: unknown, keys: string[]): T[] {
    if (Array.isArray(response)) {
      return response as T[];
    }

    if (this.isObject(response)) {
      for (const key of keys) {
        const candidate = response[key];
        if (Array.isArray(candidate)) {
          return candidate as T[];
        }
      }
    }

    return [];
  }

  private extractObject<T>(response: unknown, keys: string[]): T {
    if (this.isObject(response)) {
      for (const key of keys) {
        const candidate = response[key];
        if (this.isObject(candidate)) {
          return candidate as T;
        }
      }
      return response as T;
    }

    throw new Error('Invalid API response payload');
  }

  private normalizeStats(source: Record<string, unknown>): Stats {
    return {
      totalUsers: this.readNumber(source, ['totalUsers', 'total_users']),
      totalDevices: this.readNumber(source, ['totalDevices', 'total_devices']),
      totalWipeJobs: this.readNumber(source, ['totalWipeJobs', 'total_wipe_jobs', 'devices_wiped']),
      completedWipeJobs: this.readNumber(source, ['completedWipeJobs', 'completed_wipe_jobs', 'successful_wipes', 'devices_wiped']),
      failedWipeJobs: this.readNumber(source, ['failedWipeJobs', 'failed_wipe_jobs', 'failed_jobs']),
      totalCertificates: this.readNumber(source, ['totalCertificates', 'total_certificates', 'certificates_generated', 'certificates']),
      devices_wiped: this.readNumber(source, ['devices_wiped', 'totalWipeJobs', 'total_wipe_jobs']),
      successful_wipes: this.readNumber(source, ['successful_wipes', 'completedWipeJobs', 'completed_wipe_jobs', 'devices_wiped']),
      failed_jobs: this.readNumber(source, ['failed_jobs', 'failedWipeJobs', 'failed_wipe_jobs']),
      certificates: this.readNumber(source, ['certificates_generated', 'certificates', 'totalCertificates', 'total_certificates']),
      certificates_generated: this.readNumber(source, ['certificates_generated', 'certificates', 'totalCertificates', 'total_certificates']),
      active_jobs: this.readNumber(source, ['active_jobs', 'running_jobs', 'activeJobs'])
    };
  }

  private readNumber(source: Record<string, unknown>, keys: string[]): number | undefined {
    for (const key of keys) {
      const value = source[key];
      if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
      }
      if (typeof value === 'string') {
        const parsed = Number(value);
        if (!Number.isNaN(parsed) && Number.isFinite(parsed)) {
          return parsed;
        }
      }
    }

    return undefined;
  }

  private readString(source: Record<string, unknown>, keys: string[]): string | null {
    for (const key of keys) {
      const value = source[key];
      if (typeof value === 'string' && value.trim()) {
        return value;
      }
    }

    return null;
  }

  private isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
  }

  private handleError(error: unknown, operation: string): Observable<never> {
    const defaultMessage = `Unable to ${operation}.`;

    if (error instanceof HttpErrorResponse) {
      const backendMessage = this.readBackendMessage(error.error);
      const message = backendMessage ?? error.message ?? defaultMessage;
      return throwError(() => new Error(message));
    }

    if (error instanceof Error) {
      return throwError(() => error);
    }

    return throwError(() => new Error(defaultMessage));
  }

  private readBackendMessage(errorBody: unknown): string | null {
    if (!this.isObject(errorBody)) {
      return null;
    }

    const knownKeys = ['message', 'error', 'detail'];
    for (const key of knownKeys) {
      const value = errorBody[key];
      if (typeof value === 'string' && value.trim()) {
        return value;
      }
    }

    return null;
  }
}
