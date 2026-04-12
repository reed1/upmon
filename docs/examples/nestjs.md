# Access Log — NestJS

NestJS implementation using a global interceptor and `better-sqlite3`. See [access-log-writing.md](../access-log-writing.md) for schema and rules.

## Differences from Other Examples

- **Interceptor instead of middleware** — NestJS interceptors have access to the execution context, making it easy to capture response status and exceptions in the same RxJS pipeline.
- **`better-sqlite3`** — Synchronous SQLite driver for Node. Prepared statements are created once at init and reused for every insert.
- **Multer file extraction** — Handles both single-file (`req.file`) and multi-file (`req.files` as array or field map) uploads from Multer.
- **Native app support** — Reads `X-Client-Type`, `X-OS`, and `X-App-Version` headers for mobile clients.

## AccessLoggerService

Manages the SQLite connection, schema, and prepared insert statement. Register as a module-level provider.

`src/common/services/access-logger.service.ts`:

```ts
import {
  Injectable,
  Logger,
  OnModuleDestroy,
  OnModuleInit,
} from '@nestjs/common';
import Database, { Statement } from 'better-sqlite3';
import * as path from 'path';
import * as fs from 'fs';

export interface ExceptionInfo {
  class: string;
  message: string;
  is_unexpected: boolean;
  traceback: string[] | null;
}

export interface FileInfo {
  fieldname: string;
  originalname: string;
  mimetype: string;
  size: number;
}

export interface AccessLogEntry {
  epoch_sec: number;
  client_ip: string;
  method: string;
  path: string;
  query: Record<string, unknown> | null;
  body: unknown;
  user_id: number | null;
  status_code: number | null;
  duration_ms: number;
  user_agent: string | null;
  os: string | null;
  client_type: string;
  app_version: string | null;
  files: FileInfo[] | null;
  exception: ExceptionInfo | null;
}

@Injectable()
export class AccessLoggerService implements OnModuleInit, OnModuleDestroy {
  private readonly nestLogger = new Logger(AccessLoggerService.name);
  private readonly dbDir = path.join(process.cwd(), 'run', 'access-log');
  private readonly dbPath = path.join(this.dbDir, 'access-log.db');
  private db: Database.Database;
  private insertStmt: Statement;

  onModuleInit() {
    fs.mkdirSync(this.dbDir, { recursive: true });

    this.db = new Database(this.dbPath);

    this.db.pragma('journal_mode = WAL');
    this.db.pragma('synchronous = NORMAL');
    this.db.pragma('cache_size = -2000');
    this.db.pragma('auto_vacuum = INCREMENTAL');
    this.db.pragma('busy_timeout = 5000');

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS access_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        epoch_sec INTEGER NOT NULL,
        client_ip TEXT NOT NULL,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        query TEXT,
        body TEXT,
        user_id INTEGER,
        status_code INTEGER,
        duration_ms REAL NOT NULL,
        user_agent TEXT,
        os TEXT,
        client_type TEXT NOT NULL,
        app_version TEXT,
        files TEXT,
        exception_class TEXT,
        exception_message TEXT,
        exception_is_unexpected INTEGER,
        exception_traceback TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_access_log_epoch_sec
        ON access_log (epoch_sec);
      CREATE INDEX IF NOT EXISTS idx_access_log_unexpected_exceptions
        ON access_log (epoch_sec) WHERE exception_is_unexpected = 1;
    `);

    this.insertStmt = this.db.prepare(`
      INSERT INTO access_log (
        epoch_sec, client_ip, method, path, query, body,
        user_id, status_code, duration_ms, user_agent,
        os, client_type, app_version, files,
        exception_class, exception_message, exception_is_unexpected, exception_traceback
      ) VALUES (
        @epoch_sec, @client_ip, @method, @path, @query, @body,
        @user_id, @status_code, @duration_ms, @user_agent,
        @os, @client_type, @app_version, @files,
        @exception_class, @exception_message, @exception_is_unexpected, @exception_traceback
      )
    `);

    this.nestLogger.log(`SQLite access log initialized at ${this.dbPath}`);
  }

  onModuleDestroy() {
    this.db.close();
  }

  log(entry: AccessLogEntry): void {
    const ex = entry.exception;
    this.insertStmt.run({
      epoch_sec: entry.epoch_sec,
      client_ip: entry.client_ip,
      method: entry.method,
      path: entry.path,
      query: entry.query ? JSON.stringify(entry.query) : null,
      body: entry.body != null ? JSON.stringify(entry.body) : null,
      user_id: entry.user_id,
      status_code: entry.status_code,
      duration_ms: entry.duration_ms,
      user_agent: entry.user_agent,
      os: entry.os,
      client_type: entry.client_type,
      app_version: entry.app_version,
      files: entry.files ? JSON.stringify(entry.files) : null,
      exception_class: ex?.class ?? null,
      exception_message: ex?.message ?? null,
      exception_is_unexpected: ex ? (ex.is_unexpected ? 1 : 0) : null,
      exception_traceback: ex?.traceback ? JSON.stringify(ex.traceback) : null,
    });
  }
}
```

## Interceptor

Global interceptor that wraps every request. Uses RxJS `tap` for success and `catchError` for exceptions.

`src/common/interceptors/access-log.interceptor.ts`:

```ts
import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
  HttpException,
} from '@nestjs/common';
import { Observable, throwError } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { Request, Response } from 'express';
import {
  AccessLoggerService,
  AccessLogEntry,
  ExceptionInfo,
  FileInfo,
} from '../services/access-logger.service';
import { CurrentUserService } from '../../context/services/current-user.service';

const EXCLUDED_METHODS = new Set(['OPTIONS']);
const EXCLUDED_PATHS = new Set(['/health', '/health/agent']);

@Injectable()
export class AccessLogInterceptor implements NestInterceptor {
  constructor(
    private readonly accessLogger: AccessLoggerService,
    private readonly currentUserService: CurrentUserService,
  ) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    if (process.env.ACCESS_LOG_ENABLED !== 'true') {
      return next.handle();
    }

    const ctx = context.switchToHttp();
    const request = ctx.getRequest<Request>();
    const response = ctx.getResponse<Response>();

    if (
      EXCLUDED_METHODS.has(request.method) ||
      EXCLUDED_PATHS.has(request.path)
    ) {
      return next.handle();
    }

    const startTime = performance.now();
    const clientInfo = this.getClientInfo(request);
    const appVersion =
      clientInfo.client_type === 'app'
        ? ((request.headers['x-app-version'] as string) ?? null)
        : null;

    const baseEntry = {
      client_ip: this.getClientIp(request),
      method: request.method,
      path: request.path,
      query: Object.keys(request.query).length > 0 ? request.query : null,
      body: this.sanitizeBody(request.body),
      user_id: this.currentUserService.user?.id ?? null,
      user_agent: request.headers['user-agent'] ?? null,
      os: clientInfo.os,
      client_type: clientInfo.client_type,
      app_version: appVersion,
    };

    return next.handle().pipe(
      tap(() => {
        const durationMs = performance.now() - startTime;
        const entry: AccessLogEntry = {
          epoch_sec: Math.floor(Date.now() / 1000),
          ...baseEntry,
          status_code: response.statusCode,
          duration_ms: Math.round(durationMs * 100) / 100,
          files: this.extractFileInfo(request),
          exception: null,
        };
        this.accessLogger.log(entry);
      }),
      catchError((error: Error) => {
        const durationMs = performance.now() - startTime;
        const isUnexpected = !(error instanceof HttpException);
        const statusCode = isUnexpected ? 500 : error.getStatus();

        if (statusCode === 404 && baseEntry.user_id === null) {
          return throwError(() => error);
        }

        const exceptionInfo: ExceptionInfo = {
          class: error.constructor.name,
          message: error.message,
          is_unexpected: isUnexpected,
          traceback: isUnexpected ? this.parseStackTrace(error.stack) : null,
        };

        const entry: AccessLogEntry = {
          epoch_sec: Math.floor(Date.now() / 1000),
          ...baseEntry,
          status_code: statusCode,
          duration_ms: Math.round(durationMs * 100) / 100,
          files: this.extractFileInfo(request),
          exception: exceptionInfo,
        };
        this.accessLogger.log(entry);

        return throwError(() => error);
      }),
    );
  }

  private getClientIp(request: Request): string {
    const forwarded = request.headers['x-forwarded-for'];
    if (forwarded) {
      const ip = Array.isArray(forwarded)
        ? forwarded[0]
        : forwarded.split(',')[0];
      return ip.trim();
    }
    return request.ip ?? request.socket.remoteAddress ?? '-';
  }

  private sanitizeBody(body: unknown): unknown {
    if (!body || typeof body !== 'object') {
      return body;
    }
    // Add field redaction here for your app's sensitive fields
    return body;
  }

  private parseStackTrace(stack: string | undefined): string[] | null {
    if (!stack) return null;
    const lines = stack.split('\n').slice(1);
    return lines.map((line) => line.trim()).filter((line) => line.length > 0);
  }

  private extractFileInfo(request: Request): FileInfo[] | null {
    const multerRequest = request as Request & {
      file?: Express.Multer.File;
      files?: Express.Multer.File[] | Record<string, Express.Multer.File[]>;
    };

    const files: FileInfo[] = [];

    if (multerRequest.file) {
      files.push(this.mapFileToInfo(multerRequest.file));
    }

    if (multerRequest.files) {
      if (Array.isArray(multerRequest.files)) {
        for (const file of multerRequest.files) {
          files.push(this.mapFileToInfo(file));
        }
      } else {
        for (const fieldFiles of Object.values(multerRequest.files)) {
          for (const file of fieldFiles) {
            files.push(this.mapFileToInfo(file));
          }
        }
      }
    }

    return files.length > 0 ? files : null;
  }

  private mapFileToInfo(file: Express.Multer.File): FileInfo {
    return {
      fieldname: file.fieldname,
      originalname: file.originalname,
      mimetype: file.mimetype,
      size: file.size,
    };
  }

  private getClientInfo(request: Request): {
    os: string | null;
    client_type: 'app' | 'browser';
  } {
    const clientType = request.headers['x-client-type'] as string | undefined;

    if (clientType === 'app') {
      const os = (request.headers['x-os'] as string | undefined) ?? null;
      return { os, client_type: 'app' };
    }

    return { os: this.parseOsFromUserAgent(request), client_type: 'browser' };
  }

  private parseOsFromUserAgent(request: Request): string | null {
    const ua = request.headers['user-agent'] ?? '';
    if (ua.includes('Android')) return 'android';
    if (ua.includes('iPhone') || ua.includes('iPad')) return 'ios';
    if (ua.includes('Macintosh')) return 'macos';
    if (ua.includes('Windows')) return 'windows';
    if (ua.includes('CrOS')) return 'chromeos';
    if (ua.includes('Linux')) return 'linux';
    return null;
  }
}
```

## Registering

Register as a global interceptor in your app module. `CurrentUserService` is a request-scoped service that provides the authenticated user — replace with your own auth context.

```ts
import { APP_INTERCEPTOR } from '@nestjs/core';

@Module({
  providers: [
    AccessLoggerService,
    {
      provide: APP_INTERCEPTOR,
      useClass: AccessLogInterceptor,
    },
  ],
})
export class AppModule {}
```

## Environment

Enable via environment variable:

```
ACCESS_LOG_ENABLED=true
```

## Dependencies

```bash
npm install better-sqlite3
npm install -D @types/better-sqlite3
```
