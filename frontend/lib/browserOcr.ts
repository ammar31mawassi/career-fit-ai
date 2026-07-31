import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  PDFPageProxy,
  RenderTask
} from "pdfjs-dist";
import type Tesseract from "tesseract.js";
import {
  describeBrowserOcrCoverage,
  planBrowserOcrCoverage,
  planBrowserOcrRaster,
  validateBrowserOcrFile,
  validateBrowserOcrRasterTotal
} from "@/lib/browser-ocr-policy.mjs";

export type BrowserOcrProgress = {
  progress: number;
  page: number;
  processedPages: number;
  totalPages: number;
  truncated: boolean;
  detail: string;
  stage: "preparing" | "rendering" | "recognizing" | "complete";
};

export type BrowserOcrResult = {
  text: string;
  confidence: number;
  engine: "tesseract.js";
  pages: Array<{ page_number: number; confidence: number; word_count: number }>;
  processed_pages: number;
  total_pages: number;
  omitted_pages: number;
  truncated: boolean;
  coverage_detail: string;
};

type PagePlan = {
  page: PDFPageProxy;
  pageNumber: number;
  viewportScale: number;
  width: number;
  height: number;
};

export async function recognizePdfInBrowser(
  file: File,
  onProgress?: (update: BrowserOcrProgress) => void,
  signal?: AbortSignal
): Promise<BrowserOcrResult> {
  const filePolicy = validateBrowserOcrFile(file);
  if (!filePolicy.ok) throw new Error(filePolicy.error);
  throwIfAborted(signal);

  let loadingTask: PDFDocumentLoadingTask | null = null;
  let pdf: PDFDocumentProxy | null = null;
  let worker: Tesseract.Worker | null = null;
  let renderTask: RenderTask | null = null;
  let workerTermination: Promise<unknown> | null = null;
  let documentDestruction: Promise<unknown> | null = null;
  const openedPages: PDFPageProxy[] = [];
  const cleanedPages = new WeakSet<PDFPageProxy>();

  const terminateWorker = () => {
    if (!worker || workerTermination) return workerTermination;
    workerTermination = Promise.resolve(worker.terminate());
    return workerTermination;
  };
  const destroyDocument = () => {
    if (!loadingTask || documentDestruction) return documentDestruction;
    documentDestruction = Promise.resolve(loadingTask.destroy());
    return documentDestruction;
  };
  const cancelActiveRender = () => {
    const activeRender = renderTask;
    if (activeRender) activeRender.cancel();
  };
  const cleanupPage = (page: PDFPageProxy) => {
    if (cleanedPages.has(page)) return;
    cleanedPages.add(page);
    page.cleanup();
  };
  const stopActiveWork = () => {
    cancelActiveRender();
    void terminateWorker()?.catch(() => undefined);
    void destroyDocument()?.catch(() => undefined);
  };
  const onAbort = () => stopActiveWork();
  signal?.addEventListener("abort", onAbort, { once: true });

  try {
    const [{ getDocument, GlobalWorkerOptions }, { createWorker }] = await waitForAbortable(
      Promise.all([import("pdfjs-dist"), import("tesseract.js")]),
      signal
    );
    throwIfAborted(signal);

    GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url
    ).toString();

    const fileBytes = await waitForAbortable(file.arrayBuffer(), signal);
    throwIfAborted(signal);
    loadingTask = getDocument({ data: new Uint8Array(fileBytes) });
    pdf = await waitForAbortable(loadingTask.promise, signal);
    throwIfAborted(signal);

    const coverage = planBrowserOcrCoverage(pdf.numPages);
    const coverageDetail = describeBrowserOcrCoverage(coverage);
    publishProgress(onProgress, signal, {
      progress: 0.02,
      page: 1,
      processedPages: coverage.processedPages,
      totalPages: coverage.totalPages,
      truncated: coverage.truncated,
      detail: coverage.truncated
        ? `Preparing local OCR. ${coverageDetail}`
        : "Preparing the local OCR engine",
      stage: "preparing"
    });

    const plans: PagePlan[] = [];
    const rasterPlans: Array<{ pixels: number }> = [];
    for (let pageNumber = 1; pageNumber <= coverage.processedPages; pageNumber += 1) {
      throwIfAborted(signal);
      const page = await waitForAbortable(pdf.getPage(pageNumber), signal);
      openedPages.push(page);
      const sourceViewport = page.getViewport({ scale: 1 });
      const raster = planBrowserOcrRaster(sourceViewport.width, sourceViewport.height);
      plans.push({
        page,
        pageNumber,
        viewportScale: raster.viewportScale,
        width: raster.width,
        height: raster.height
      });
      rasterPlans.push({ pixels: raster.pixels });
    }
    const aggregatePolicy = validateBrowserOcrRasterTotal(rasterPlans);
    if (!aggregatePolicy.ok) throw new Error(aggregatePolicy.error);
    throwIfAborted(signal);

    let activePage = 1;
    let lastLoggerPage = 0;
    let lastLoggerMilestone = -1;
    const workerPromise = createWorker(["eng", "heb", "ara"], 1, {
      logger(message) {
        if (message.status !== "recognizing text" || signal?.aborted) return;
        const milestone = Math.floor(Math.max(0, Math.min(1, message.progress)) * 4);
        if (lastLoggerPage === activePage && milestone <= lastLoggerMilestone) return;
        lastLoggerPage = activePage;
        lastLoggerMilestone = milestone;
        const completed = activePage - 1;
        publishProgress(onProgress, signal, {
          progress: Math.min(
            0.98,
            (completed + Math.max(0, Math.min(1, message.progress))) / coverage.processedPages
          ),
          page: activePage,
          processedPages: coverage.processedPages,
          totalPages: coverage.totalPages,
          truncated: coverage.truncated,
          detail: pageProgressDetail("Reading", activePage, coverage),
          stage: "recognizing"
        });
      }
    });
    void workerPromise.then((createdWorker) => {
      if (!signal?.aborted) return;
      worker = createdWorker;
      return terminateWorker();
    }).catch(() => undefined);
    worker = await waitForAbortable(workerPromise, signal);
    throwIfAborted(signal);

    const pages: BrowserOcrResult["pages"] = [];
    const textParts: string[] = [];
    let weightedConfidence = 0;
    let totalWords = 0;

    for (const plan of plans) {
      activePage = plan.pageNumber;
      lastLoggerPage = 0;
      lastLoggerMilestone = -1;
      publishProgress(onProgress, signal, {
        progress: (plan.pageNumber - 1) / coverage.processedPages,
        page: plan.pageNumber,
        processedPages: coverage.processedPages,
        totalPages: coverage.totalPages,
        truncated: coverage.truncated,
        detail: pageProgressDetail("Rendering", plan.pageNumber, coverage),
        stage: "rendering"
      });

      const viewport = plan.page.getViewport({ scale: plan.viewportScale });
      const canvas = document.createElement("canvas");
      canvas.width = plan.width;
      canvas.height = plan.height;
      try {
        const context = canvas.getContext("2d", { alpha: false });
        if (!context) throw new Error("This browser could not prepare the PDF for OCR.");
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, canvas.width, canvas.height);
        renderTask = plan.page.render({ canvas, canvasContext: context, viewport });
        await waitForAbortable(renderTask.promise, signal);
        renderTask = null;
        throwIfAborted(signal);

        const result = await waitForAbortable(worker.recognize(canvas), signal);
        throwIfAborted(signal);
        const text = result.data.text.trim();
        const wordCount = text.split(/\s+/u).filter(Boolean).length;
        const confidence = Math.max(0, Math.min(1, result.data.confidence / 100));
        pages.push({ page_number: plan.pageNumber, confidence, word_count: wordCount });
        if (text) textParts.push(`Page ${plan.pageNumber}\n${text}`);
        weightedConfidence += confidence * Math.max(1, wordCount);
        totalWords += Math.max(1, wordCount);
      } finally {
        renderTask?.cancel();
        renderTask = null;
        cleanupPage(plan.page);
        canvas.width = 1;
        canvas.height = 1;
      }
    }

    const text = textParts.join("\n\n").trim();
    if (meaningfulCharacterCount(text) < 80) {
      throw new Error(
        "Local OCR could not recover enough readable text. Try a clearer scan or a text-based PDF."
      );
    }
    publishProgress(onProgress, signal, {
      progress: 1,
      page: coverage.processedPages,
      processedPages: coverage.processedPages,
      totalPages: coverage.totalPages,
      truncated: coverage.truncated,
      detail: coverageDetail,
      stage: "complete"
    });
    return {
      text,
      confidence: totalWords ? weightedConfidence / totalWords : 0,
      engine: "tesseract.js",
      pages,
      processed_pages: coverage.processedPages,
      total_pages: coverage.totalPages,
      omitted_pages: coverage.omittedPages,
      truncated: coverage.truncated,
      coverage_detail: coverageDetail
    };
  } finally {
    signal?.removeEventListener("abort", onAbort);
    cancelActiveRender();
    for (const page of openedPages) cleanupPage(page);
    await Promise.allSettled([
      terminateWorker() ?? Promise.resolve(),
      destroyDocument() ?? Promise.resolve()
    ]);
  }
}

function pageProgressDetail(
  action: "Reading" | "Rendering",
  page: number,
  coverage: {
    processedPages: number;
    totalPages: number;
    truncated: boolean;
  }
) {
  const processed = `${action} page ${page} of ${coverage.processedPages} on this device`;
  return coverage.truncated
    ? `${processed} (${coverage.totalPages} pages in the PDF)`
    : processed;
}

function publishProgress(
  onProgress: ((update: BrowserOcrProgress) => void) | undefined,
  signal: AbortSignal | undefined,
  update: BrowserOcrProgress
) {
  if (!signal?.aborted) onProgress?.(update);
}

function waitForAbortable<T>(promise: PromiseLike<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return Promise.resolve(promise);
  if (signal.aborted) return Promise.reject(abortError());
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => {
      signal.removeEventListener("abort", onAbort);
      reject(abortError());
    };
    signal.addEventListener("abort", onAbort, { once: true });
    Promise.resolve(promise).then(
      (value) => {
        signal.removeEventListener("abort", onAbort);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener("abort", onAbort);
        reject(error);
      }
    );
  });
}

function throwIfAborted(signal?: AbortSignal) {
  if (signal?.aborted) throw abortError();
}

function abortError() {
  return new DOMException("Local OCR was stopped.", "AbortError");
}

function meaningfulCharacterCount(text: string) {
  return Array.from(text).filter((character) => /[\p{L}\p{N}]/u.test(character)).length;
}
