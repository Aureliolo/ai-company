package cmd

import (
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/diagnostics"
)

func TestClassifyDoctor(t *testing.T) {
	t.Parallel()

	boolPtr := func(v bool) *bool { return &v }

	tests := []struct {
		name       string
		report     diagnostics.Report
		wantStatus doctorStatus
		wantCount  int // expected number of issues
	}{
		{
			name: "all healthy",
			report: diagnostics.Report{
				HealthStatus: "200",
				ContainerSummary: []diagnostics.ContainerDetail{
					{Name: "backend", Health: "healthy"},
					{Name: "web", Health: "healthy"},
				},
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorHealthy,
			wantCount:  0,
		},
		{
			name: "backend unreachable",
			report: diagnostics.Report{
				HealthStatus:      "unreachable",
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "backend unhealthy status code",
			report: diagnostics.Report{
				HealthStatus:      "503",
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "container starting is warning",
			report: diagnostics.Report{
				HealthStatus: "200",
				ContainerSummary: []diagnostics.ContainerDetail{
					{Name: "backend", Health: "healthy"},
					{Name: "sandbox", State: "running", Health: "starting"},
				},
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorWarnings,
			wantCount:  1,
		},
		{
			name: "container unhealthy is error",
			report: diagnostics.Report{
				HealthStatus: "200",
				ContainerSummary: []diagnostics.ContainerDetail{
					{Name: "backend", Health: "unhealthy"},
				},
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "container exited is error",
			report: diagnostics.Report{
				HealthStatus: "200",
				ContainerSummary: []diagnostics.ContainerDetail{
					{Name: "web", State: "exited"},
				},
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "compose missing",
			report: diagnostics.Report{
				HealthStatus:      "200",
				ComposeFileExists: false,
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "compose invalid",
			report: diagnostics.Report{
				HealthStatus:      "200",
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(false),
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "port conflicts",
			report: diagnostics.Report{
				HealthStatus:      "200",
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
				PortConflicts:     []string{"8000 in use by other-process"},
			},
			wantStatus: doctorErrors,
			wantCount:  1,
		},
		{
			name: "collection errors propagated",
			report: diagnostics.Report{
				HealthStatus:      "200",
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
				Errors:            []string{"docker not found", "compose not found"},
			},
			wantStatus: doctorErrors,
			wantCount:  2,
		},
		{
			name: "errors take precedence over warnings",
			report: diagnostics.Report{
				HealthStatus: "unreachable",
				ContainerSummary: []diagnostics.ContainerDetail{
					{Name: "sandbox", State: "running", Health: "starting"},
				},
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorErrors,
			wantCount:  1, // only errors returned, warnings discarded
		},
		{
			name: "empty health status is not checked",
			report: diagnostics.Report{
				HealthStatus:      "",
				ComposeFileExists: true,
				ComposeFileValid:  boolPtr(true),
			},
			wantStatus: doctorHealthy,
			wantCount:  0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			gotStatus, gotIssues := classifyDoctor(tt.report)
			if gotStatus != tt.wantStatus {
				t.Errorf("classifyDoctor() status = %d, want %d", gotStatus, tt.wantStatus)
			}
			if len(gotIssues) != tt.wantCount {
				t.Errorf("classifyDoctor() issues count = %d, want %d: %v", len(gotIssues), tt.wantCount, gotIssues)
			}
		})
	}
}
