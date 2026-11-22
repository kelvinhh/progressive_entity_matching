// Native macOS PDF renderer; no LaTeX, browser, or third-party PDF generator.
import Foundation
import CoreGraphics
import CoreText
import ImageIO

struct Block: Decodable {
    let type: String
    let text: String?
    let rows: [[String]]?
    let widths: [Double]?
    let source: String?
    let caption: String?
    let url: String?
    let evidence: [String]?
}
struct Document: Decodable {
    let title: String
    let subtitle: String
    let status: String
    let blocks: [Block]
}

final class Renderer {
    let width: CGFloat = 595.276
    let height: CGFloat = 841.89
    let margin: CGFloat = 47
    let context: CGContext
    let root: URL
    let status: String
    var y: CGFloat = 70
    var page = 0
    var overflowWarnings: [String] = []
    var contentWidth: CGFloat { width - 2 * margin }
    let ink = CGColor(red: 0.11, green: 0.16, blue: 0.23, alpha: 1)
    let blue = CGColor(red: 0.11, green: 0.26, blue: 0.40, alpha: 1)

    init(output: URL, root: URL, status: String) {
        var box = CGRect(x: 0, y: 0, width: width, height: height)
        self.context = CGContext(output as CFURL, mediaBox: &box,
            [kCGPDFContextTitle: "Progressive Entity Matching — Focused Replication",
             kCGPDFContextCreator: "Native CoreText report renderer"] as CFDictionary)!
        self.root = root
        self.status = status
    }

    func attributed(_ text: String, size: CGFloat, bold: Bool = false,
                    mono: Bool = false, color: CGColor? = nil) -> NSAttributedString {
        let name = mono ? "Menlo-Regular" : (bold ? "HelveticaNeue-Bold" : "HelveticaNeue")
        let font = CTFontCreateWithName(name as CFString, size, nil)
        var gap: CGFloat = mono ? 2.3 : 3.0
        let paragraph = withUnsafePointer(to: &gap) { pointer -> CTParagraphStyle in
            var setting = CTParagraphStyleSetting(spec: .lineSpacingAdjustment,
                valueSize: MemoryLayout<CGFloat>.size, value: pointer)
            return CTParagraphStyleCreate(&setting, 1)
        }
        return NSAttributedString(string: text, attributes: [
            NSAttributedString.Key(kCTFontAttributeName as String): font,
            NSAttributedString.Key(kCTForegroundColorAttributeName as String): color ?? ink,
            NSAttributedString.Key(kCTParagraphStyleAttributeName as String): paragraph
        ])
    }

    func textHeight(_ text: String, width: CGFloat, size: CGFloat,
                    bold: Bool = false, mono: Bool = false) -> CGFloat {
        let framesetter = CTFramesetterCreateWithAttributedString(attributed(text, size: size, bold: bold, mono: mono))
        return ceil(CTFramesetterSuggestFrameSizeWithConstraints(framesetter, CFRange(location: 0, length: 0),
            nil, CGSize(width: width, height: 100000), nil).height) + 4
    }

    @discardableResult
    func draw(_ text: String, x: CGFloat, top: CGFloat, width: CGFloat, size: CGFloat,
              bold: Bool = false, mono: Bool = false, color: CGColor? = nil) -> CGFloat {
        let value = attributed(text, size: size, bold: bold, mono: mono, color: color)
        let h = textHeight(text, width: width, size: size, bold: bold, mono: mono)
        let framesetter = CTFramesetterCreateWithAttributedString(value)
        let box = CGRect(x: x, y: height - top - h, width: width, height: h)
        let frame = CTFramesetterCreateFrame(framesetter, CFRange(location: 0, length: value.length),
            CGPath(rect: box, transform: nil), nil)
        context.textMatrix = .identity
        CTFrameDraw(frame, context)
        let visible = CTFrameGetVisibleStringRange(frame)
        if visible.length < value.length { overflowWarnings.append("Truncated text on page \(page)") }
        return h
    }

    func newPage() {
        if page > 0 { context.endPDFPage() }
        context.beginPDFPage(nil)
        page += 1
        y = 68
        _ = draw("DSC-5003  |  TRACK 2  |  RESEARCH PAPER REPLICATION", x: margin, top: 25,
                 width: contentWidth, size: 8.1, bold: true, color: blue)
        context.setStrokeColor(CGColor(gray: 0.80, alpha: 1))
        context.setLineWidth(0.6)
        context.move(to: CGPoint(x: margin, y: height - 48))
        context.addLine(to: CGPoint(x: width - margin, y: height - 48))
        context.strokePath()
        _ = draw(status, x: margin, top: height - 31, width: contentWidth - 65, size: 7.5,
                 color: CGColor(gray: 0.42, alpha: 1))
        _ = draw("Page \(page)", x: width - margin - 50, top: height - 31, width: 50, size: 7.5,
                 color: CGColor(gray: 0.42, alpha: 1))
    }

    func ensure(_ h: CGFloat) {
        if y + h > height - 50 { newPage() }
        if h > height - 118 { overflowWarnings.append("Oversized block on page \(page)") }
    }

    func paragraph(_ text: String, size: CGFloat = 10.2, bold: Bool = false, mono: Bool = false,
                   gap: CGFloat = 9, url: String? = nil) {
        let h = textHeight(text, width: contentWidth, size: size, bold: bold, mono: mono)
        ensure(h + gap)
        if mono {
            context.setFillColor(CGColor(gray: 0.955, alpha: 1))
            context.fill(CGRect(x: margin - 5, y: height - y - h - 4, width: contentWidth + 10, height: h + 8))
        }
        _ = draw(text, x: margin, top: y, width: contentWidth, size: size, bold: bold, mono: mono)
        if let address = url, let target = URL(string: address) {
            context.setURL(target as CFURL, for: CGRect(x: margin, y: height - y - h, width: contentWidth, height: h))
        }
        y += h + gap
    }

    func table(_ rows: [[String]], widths: [Double]?) {
        guard let header = rows.first, !header.isEmpty else { return }
        let weights = widths ?? Array(repeating: 1.0, count: header.count)
        let total = weights.reduce(0, +)
        let columns = weights.map { CGFloat($0 / total) * contentWidth }
        func rowHeight(_ row: [String], header: Bool) -> CGFloat {
            return (row.enumerated().map { index, value in
                textHeight(value, width: columns[index] - 12, size: 8.65, bold: header)
            }.max() ?? 14) + 11
        }
        func paint(_ row: [String], header: Bool, index: Int) {
            let h = rowHeight(row, header: header)
            context.setFillColor(header ? blue : CGColor(gray: index % 2 == 0 ? 0.955 : 1.0, alpha: 1))
            context.fill(CGRect(x: margin, y: height - y - h, width: contentWidth, height: h))
            var x = margin
            for (i, value) in row.enumerated() {
                _ = draw(value, x: x + 6, top: y + 5, width: columns[i] - 12, size: 8.65,
                         bold: header, color: header ? CGColor(gray: 1, alpha: 1) : ink)
                x += columns[i]
            }
            y += h
            context.setStrokeColor(CGColor(gray: 0.85, alpha: 1))
            context.setLineWidth(0.35)
            context.move(to: CGPoint(x: margin, y: height - y))
            context.addLine(to: CGPoint(x: width - margin, y: height - y))
            context.strokePath()
        }
        let totalHeight = rows.enumerated().reduce(CGFloat(0)) { sum, entry in
            sum + rowHeight(entry.element, header: entry.offset == 0)
        } + 12
        if totalHeight <= height - 118 { ensure(totalHeight) }
        ensure(rowHeight(header, header: true) + (rows.count > 1 ? rowHeight(rows[1], header: false) : 0))
        paint(header, header: true, index: 0)
        for (index, row) in rows.dropFirst().enumerated() {
            let h = rowHeight(row, header: false)
            if y + h > height - 50 {
                newPage()
                paint(header, header: true, index: 0)
            }
            paint(row, header: false, index: index)
        }
        y += 12
    }

    func image(_ path: String, caption: String) {
        let url = root.appendingPathComponent(path)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            fatalError("Missing report figure: \(url.path)")
        }
        let captionH = textHeight(caption, width: contentWidth, size: 8.65)
        let naturalH = contentWidth * CGFloat(image.height) / CGFloat(image.width)
        let h = min(naturalH, height - 145 - captionH)
        ensure(h + captionH + 15)
        let w = h * CGFloat(image.width) / CGFloat(image.height)
        context.draw(image, in: CGRect(x: margin + (contentWidth - w) / 2,
                                     y: height - y - h, width: w, height: h))
        y += h + 5
        paragraph(caption, size: 8.65, gap: 12)
    }

    func render(_ document: Document) {
        newPage()
        for (index, block) in document.blocks.enumerated() {
            var followingHeight: CGFloat = 45
            if index + 1 < document.blocks.count {
                let next = document.blocks[index + 1]
                if next.type == "paragraph", let text = next.text {
                    followingHeight = textHeight(text, width: contentWidth, size: 10.2) + 10
                } else if next.type == "table", let rows = next.rows, let first = rows.first {
                    let weights = next.widths ?? Array(repeating: 1.0, count: first.count)
                    let total = weights.reduce(0, +)
                    let columns = weights.map { CGFloat($0 / total) * contentWidth }
                    followingHeight = rows.enumerated().reduce(CGFloat(0)) { sum, item in
                        sum + (item.element.enumerated().map { column, value in
                            textHeight(value, width: columns[column] - 12, size: 8.65, bold: item.offset == 0)
                        }.max() ?? 14) + 11
                    } + 12
                }
            }
            switch block.type {
            case "title":
                y += 20
                paragraph(block.text ?? "", size: 24, bold: true, gap: 14)
            case "subtitle": paragraph(block.text ?? "", size: 11, gap: 13)
            case "heading":
                ensure(min(followingHeight + 38, height - 120))
                y += 7
                paragraph(block.text ?? "", size: 14.1, bold: true, gap: 8)
            case "subheading":
                ensure(min(followingHeight + 30, height - 120))
                paragraph(block.text ?? "", size: 11.2, bold: true, gap: 6)
            case "paragraph": paragraph(block.text ?? "", url: block.url)
            case "note": paragraph(block.text ?? "", size: 9, gap: 10)
            case "code": paragraph(block.text ?? "", size: 7.65, mono: true, gap: 12)
            case "table": table(block.rows ?? [], widths: block.widths)
            case "figure": image(block.source ?? "", caption: block.caption ?? "")
            case "pagebreak": if y > 75 { newPage() }
            default: fatalError("Unknown report block \(block.type)")
            }
        }
        context.endPDFPage()
        context.closePDF()
    }
}

guard CommandLine.arguments.count == 3 else {
    fatalError("Usage: swift render_pdf.swift report.json output.pdf")
}
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
let document = try JSONDecoder().decode(Document.self, from: Data(contentsOf: input))
let renderer = Renderer(output: output, root: input.deletingLastPathComponent(), status: document.status)
renderer.render(document)
let audit: [String: Any] = ["pages": renderer.page, "overflow_warnings": renderer.overflowWarnings,
                          "renderer": "CoreGraphics / CoreText", "page_size": "A4"]
let auditURL = output.deletingLastPathComponent().appendingPathComponent("layout_validation.json")
try JSONSerialization.data(withJSONObject: audit, options: [.prettyPrinted, .sortedKeys]).write(to: auditURL)
print("Rendered \(renderer.page) pages; overflow warnings: \(renderer.overflowWarnings.count)")
