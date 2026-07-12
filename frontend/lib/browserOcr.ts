export type BrowserOcrProgress = {
  progress: number;
  page: number;
  totalPages: number;
  detail: string;
};

export type BrowserOcrResult = {
  text: string;
  confidence: number;
  engine: "tesseract.js";
  pages: Array<{ page_number: number; confidence: number; word_count: number }>;
};

const MAX_PAGES = 8;
const MAX_RENDER_EDGE = 2200;

export async function recognizePdfInBrowser(
  file: File,
  onProgress?: (update: BrowserOcrProgress) => void
): Promise<BrowserOcrResult> {
  const [{ getDocument, GlobalWorkerOptions }, { createWorker }] = await Promise.all([
    import("pdfjs-dist"),
    import("tesseract.js")
  ]);

  GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url
  ).toString();

  const loadingTask = getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
  const pdf = await loadingTask.promise;
  const totalPages = Math.min(pdf.numPages, MAX_PAGES);
  let activePage = 1;
  onProgress?.({ progress: 0.02, page: 1, totalPages, detail: "Preparing local OCR engine" });

  const worker = await createWorker(["eng", "heb", "ara"], 1, {
    logger(message) {
      if (message.status !== "recognizing text") return;
      const completed = activePage - 1;
      onProgress?.({
        progress: Math.min(0.98, (completed + message.progress) / totalPages),
        page: activePage,
        totalPages,
        detail: `Reading page ${activePage} of ${totalPages} on this device`
      });
    }
  });

  const pages: BrowserOcrResult["pages"] = [];
  const textParts: string[] = [];
  let weightedConfidence = 0;
  let totalWords = 0;

  try {
    for (let pageNumber = 1; pageNumber <= totalPages; pageNumber += 1) {
      activePage = pageNumber;
      onProgress?.({
        progress: (pageNumber - 1) / totalPages,
        page: pageNumber,
        totalPages,
        detail: `Rendering page ${pageNumber} privately in your browser`
      });
      const page = await pdf.getPage(pageNumber);
      const baseViewport = page.getViewport({ scale: 2 });
      const edgeScale = Math.min(1, MAX_RENDER_EDGE / Math.max(baseViewport.width, baseViewport.height));
      const viewport = page.getViewport({ scale: 2 * edgeScale });
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.floor(viewport.width));
      canvas.height = Math.max(1, Math.floor(viewport.height));
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("This browser could not prepare the PDF for OCR.");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      await page.render({ canvas, canvasContext: context, viewport }).promise;

      const result = await worker.recognize(canvas);
      const text = result.data.text.trim();
      const wordCount = text.split(/\s+/u).filter(Boolean).length;
      const confidence = Math.max(0, Math.min(1, result.data.confidence / 100));
      pages.push({ page_number: pageNumber, confidence, word_count: wordCount });
      if (text) textParts.push(`Page ${pageNumber}\n${text}`);
      weightedConfidence += confidence * Math.max(1, wordCount);
      totalWords += Math.max(1, wordCount);
      page.cleanup();
      canvas.width = 1;
      canvas.height = 1;
    }
  } finally {
    await worker.terminate();
    await loadingTask.destroy();
  }

  const text = textParts.join("\n\n").trim();
  if (meaningfulCharacterCount(text) < 80) {
    throw new Error("Local OCR could not recover enough readable text. Try a clearer scan or a text-based PDF.");
  }
  onProgress?.({ progress: 1, page: totalPages, totalPages, detail: "Local OCR complete" });
  return {
    text,
    confidence: totalWords ? weightedConfidence / totalWords : 0,
    engine: "tesseract.js",
    pages
  };
}

function meaningfulCharacterCount(text: string) {
  return Array.from(text).filter((character) => /[\p{L}\p{N}]/u.test(character)).length;
}
