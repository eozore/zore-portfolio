# Domain Entities — Video Editor API

> Referência: requirements.md, business-rules.md

## Core Entities

### Project

O conceito central. Representa um "job" de edição de vídeo com memória persistida.

```typescript
interface Project {
  id: string;                    // UUID v4
  status: ProjectStatus;
  created_at: Date;
  updated_at: Date;
  
  // Inputs
  input: {
    video_path: string;          // Path local ou GCS URI do MP4
    html_path: string;           // Path local ou GCS URI do HTML
    video_duration_sec: number;  // Duração detectada via ffprobe
    total_slides: number;        // Contagem de <section class="slide">
  };
  
  // Pipeline state
  progress: StepProgress;
  
  // Cached intermediates
  cache: {
    transcript_path?: string;    // Path do transcript.json
    slides_h_dir?: string;       // Dir dos slides horizontais exportados
    slides_v_dir?: string;       // Dir dos slides verticais exportados
    alignments_path?: string;    // Path do alignments.json
  };
  
  // Outputs
  outputs?: {
    horizontal_url: string;      // GCS signed URL ou path local
    vertical_url: string;        // GCS signed URL ou path local
    expires_at: Date;            // Expiração dos URLs
  };
  
  // Error tracking
  error?: {
    step: PipelineStep;
    message: string;
    timestamp: Date;
  };
}
```

### ProjectStatus (State Machine)

```typescript
type ProjectStatus =
  | 'created'
  | 'transcribing'
  | 'exporting_slides'
  | 'aligning'
  | 'composing_horizontal'
  | 'composing_vertical'
  | 'cutting_horizontal'
  | 'cutting_vertical'
  | 'uploading_results'
  | 'completed'
  | 'failed';
```

**Transições válidas:**
```
created → transcribing → exporting_slides → aligning → 
composing_horizontal → composing_vertical → 
cutting_horizontal → cutting_vertical → 
uploading_results → completed

(qualquer status) → failed
```

### PipelineStep

```typescript
type PipelineStep =
  | 'upload'
  | 'stt'
  | 'slide_export'
  | 'alignment'
  | 'compose_horizontal'
  | 'compose_vertical'
  | 'jump_cuts_horizontal'
  | 'jump_cuts_vertical'
  | 'storage';
```

### StepProgress

```typescript
interface StepProgress {
  current_step: PipelineStep;
  percent: number;              // 0-100 (estimado por step)
  message: string;              // Mensagem human-readable
  steps_completed: PipelineStep[];
}
```

## Data Transfer Objects

### TranscriptSegment

```typescript
interface TranscriptWord {
  word: string;
  start: number;   // seconds
  end: number;     // seconds
}

interface TranscriptSegment {
  text: string;          // Texto completo do segment
  start: number;        // Start time (seconds)
  end: number;          // End time (seconds)  
  words: TranscriptWord[];
}

type TranscriptResult = TranscriptSegment[];
```

### SlideAlignment

```typescript
interface SlideAlignment {
  slide_index: number;   // 1-based
  start_time: number;    // seconds
  end_time: number;      // seconds
}

interface AlignmentResult {
  alignments: SlideAlignment[];
}
```

### SlideDescription

```typescript
interface SlideDescription {
  index: number;         // 1-based
  text: string;          // Texto extraído do HTML (semântica)
}
```

### JumpCutSegment

```typescript
type JumpCutSegment = [number, number]; // [start_sec, end_sec]
```

## Module Interfaces

### ISttModule

```typescript
interface ISttModule {
  transcribe(videoPath: string, options?: SttOptions): Promise<TranscriptResult>;
}

interface SttOptions {
  language?: string;         // default: "pt-BR"
  cachePath?: string;        // Se fornecido, usa cache
  gcsBucket?: string;        // Bucket para upload temporário
}
```

### ISlideExportModule

```typescript
interface ISlideExportModule {
  export(htmlPath: string, options: SlideExportOptions): Promise<string[]>; // paths dos MP4s
}

interface SlideExportOptions {
  width: number;
  height: number;
  outputDir: string;
  slideDuration?: number;    // default: 10s
}
```

### IAlignmentModule

```typescript
interface IAlignmentModule {
  align(transcript: TranscriptResult, slides: SlideDescription[]): Promise<AlignmentResult>;
}
```

### IComposeModule

```typescript
interface IComposeModule {
  compose(options: ComposeOptions): Promise<string>; // path do vídeo composto
}

interface ComposeOptions {
  videoPath: string;
  alignments: SlideAlignment[];
  slidesDir: string;
  outputPath: string;
  width: number;
  height: number;
}
```

### IJumpCutsModule

```typescript
interface IJumpCutsModule {
  cut(options: JumpCutOptions): Promise<string>; // path do vídeo cortado
}

interface JumpCutOptions {
  inputVideo: string;
  outputVideo: string;
  transcript: TranscriptResult;
  minSilence?: number;       // default: 0.5s
  padding?: number;          // default: 0.2s
  maxSegments?: number;      // default: 25 (safety guard)
}
```

### IStorageModule

```typescript
interface IStorageModule {
  upload(localPath: string, destination: string): Promise<string>; // URL
  getSignedUrl(path: string, expiresIn?: number): Promise<string>;
  delete(path: string): Promise<void>;
}
```

### IProjectRepository

```typescript
interface IProjectRepository {
  create(input: ProjectInput): Promise<Project>;
  get(id: string): Promise<Project | null>;
  update(id: string, patch: Partial<Project>): Promise<void>;
  updateStatus(id: string, status: ProjectStatus): Promise<void>;
  updateProgress(id: string, progress: StepProgress): Promise<void>;
  list(options?: { limit?: number; status?: ProjectStatus }): Promise<Project[]>;
  delete(id: string): Promise<void>;
}
```

## Relationships

```
Project (1) ──── has ────── (1) TranscriptResult (cached)
Project (1) ──── has ────── (1) AlignmentResult (per run)
Project (1) ──── produces ── (2) Output Videos (horizontal + vertical)
Project (1) ──── has ────── (N) SlideClips (horizontal set + vertical set)
```

## Folder Structure per Project

```
projects/{project_id}/
├── input/
│   ├── video.mp4
│   └── deck.html
├── cache/
│   ├── transcript.json
│   ├── slides_h/
│   │   ├── slide_01.mp4
│   │   └── ...
│   └── slides_v/
│       ├── slide_01.mp4
│       └── ...
├── intermediate/
│   ├── alignments.json
│   ├── composed_h.mp4
│   └── composed_v.mp4
└── output/
    ├── final_horizontal.mp4
    └── final_vertical.mp4
```
