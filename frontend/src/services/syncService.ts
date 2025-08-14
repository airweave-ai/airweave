import { apiClient } from "@/lib/api";

export interface SyncScheduleConfig {
  type: "one-time" | "scheduled" | "incremental";
  frequency?:
    | "hourly"
    | "daily"
    | "weekly"
    | "monthly"
    | "custom"
    | "minute"
    | "5min"
    | "15min"
    | "30min";
  hour?: number;
  minute?: number;
  dayOfWeek?: number;
  dayOfMonth?: number;
  cronExpression?: string;
}

export interface ScheduleResponse {
  schedule_id: string;
  status: string;
  message: string;
  cron_expression?: string;
  running?: boolean;
  paused?: boolean;
}

export interface MinuteLevelScheduleConfig {
  cron_expression: string;
}

export class SyncService {
  /**
   * Create a minute-level schedule for a sync
   */
  static async createMinuteLevelSchedule(
    syncId: string,
    cronExpression: string
  ): Promise<ScheduleResponse> {
    const response = await apiClient.post(
      `/sync/${syncId}/minute-level-schedule`,
      {
        cron_expression: cronExpression,
      }
    );

    if (!response.ok) {
      throw new Error(
        `Failed to create minute-level schedule: ${response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Update an existing minute-level schedule
   */
  static async updateMinuteLevelSchedule(
    syncId: string,
    cronExpression: string
  ): Promise<ScheduleResponse> {
    const response = await apiClient.put(
      `/sync/${syncId}/minute-level-schedule`,
      undefined,
      {
        cron_expression: cronExpression,
      }
    );

    if (!response.ok) {
      throw new Error(
        `Failed to update minute-level schedule: ${response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Pause a minute-level schedule
   */
  static async pauseMinuteLevelSchedule(
    syncId: string
  ): Promise<ScheduleResponse> {
    const response = await apiClient.post(
      `/sync/${syncId}/minute-level-schedule/pause`
    );

    if (!response.ok) {
      throw new Error(
        `Failed to pause minute-level schedule: ${response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Resume a paused minute-level schedule
   */
  static async resumeMinuteLevelSchedule(
    syncId: string
  ): Promise<ScheduleResponse> {
    const response = await apiClient.post(
      `/sync/${syncId}/minute-level-schedule/resume`
    );

    if (!response.ok) {
      throw new Error(
        `Failed to resume minute-level schedule: ${response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Delete a minute-level schedule
   */
  static async deleteMinuteLevelSchedule(
    syncId: string
  ): Promise<ScheduleResponse> {
    const response = await apiClient.delete(
      `/sync/${syncId}/minute-level-schedule`
    );

    if (!response.ok) {
      throw new Error(
        `Failed to delete minute-level schedule: ${response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Get information about a minute-level schedule
   */
  static async getMinuteLevelScheduleInfo(
    syncId: string
  ): Promise<ScheduleResponse | null> {
    const response = await apiClient.get(
      `/sync/${syncId}/minute-level-schedule`
    );

    if (response.status === 404) {
      return null; // No schedule exists
    }

    if (!response.ok) {
      throw new Error(
        `Failed to get minute-level schedule info: ${response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Run a sync manually
   */
  static async runSync(syncId: string): Promise<any> {
    const response = await apiClient.post(`/sync/${syncId}/run`);

    if (!response.ok) {
      throw new Error(`Failed to run sync: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get sync jobs for a specific sync
   */
  static async getSyncJobs(syncId: string): Promise<any[]> {
    const response = await apiClient.get(`/sync/${syncId}/jobs`);

    if (!response.ok) {
      throw new Error(`Failed to get sync jobs: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get a specific sync job
   */
  static async getSyncJob(syncId: string, jobId: string): Promise<any> {
    const response = await apiClient.get(`/sync/${syncId}/job/${jobId}`);

    if (!response.ok) {
      throw new Error(`Failed to get sync job: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Cancel a sync job
   */
  static async cancelSyncJob(syncId: string, jobId: string): Promise<any> {
    const response = await apiClient.post(
      `/sync/${syncId}/job/${jobId}/cancel`
    );

    if (!response.ok) {
      throw new Error(`Failed to cancel sync job: ${response.statusText}`);
    }

    return response.json();
  }
}
