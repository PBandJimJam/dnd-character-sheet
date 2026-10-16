// OCR a scanned PDF with macOS's built-in Vision text recognition, one text file per page.
//
// For books whose PDF has no text layer (pdf_text.py finds nothing). Writes
// packs/.text/<book-id>/p0001.txt ... in two-column reading order. Needs macOS 13+, no installs.
//
// Usage: tools/extract/ocr_pdf.sh <book.pdf> <book-id> [first page] [last page]  (picks a working SDK)
import Foundation
import PDFKit
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else {
    print("Usage: swift tools/extract/ocr_pdf.swift <book.pdf> <book-id> [first page] [last page]")
    exit(1)
}
guard let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    print("Couldn't open \(args[1])")
    exit(1)
}
let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
let out = root.appendingPathComponent("packs/.text/\(args[2])")
try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
let first = args.count > 3 ? Int(args[3])! : 1
let last = args.count > 4 ? Int(args[4])! : doc.pageCount

func render(_ page: PDFPage) -> CGImage? {
    let box = page.bounds(for: .mediaBox)
    let scale: CGFloat = 2.5  // about 180 dpi: enough for body text
    let w = Int(box.width * scale), h = Int(box.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    return ctx.makeImage()
}

var done = 0
for n in first...last {
    guard let page = doc.page(at: n - 1), let image = render(page) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: image, options: [:]).perform([req])
    let obs = (req.results ?? []).compactMap { o -> (CGRect, String)? in
        guard let t = o.topCandidates(1).first?.string else { return nil }
        return (o.boundingBox, t)
    }
    // Reading order: left column top to bottom, then right column. Lines wider than a column
    // (headings across the page) go with whichever column they start in.
    let left = obs.filter { $0.0.minX < 0.48 }.sorted { $0.0.maxY > $1.0.maxY }
    let right = obs.filter { $0.0.minX >= 0.48 }.sorted { $0.0.maxY > $1.0.maxY }
    let text = (left + right).map { $0.1 }.joined(separator: "\n")
    try? text.write(to: out.appendingPathComponent(String(format: "p%04d.txt", n)), atomically: true, encoding: .utf8)
    done += 1
    if done % 20 == 0 { print("\(args[2]): \(done) pages"); fflush(stdout) }
}
print("\(args[2]): OCR'd \(done) pages -> packs/.text/\(args[2])")
