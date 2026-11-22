import Foundation
import PDFKit
import AppKit

guard CommandLine.arguments.count == 3 else { fatalError("Usage: render_preview.swift input.pdf output_directory") }
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let destination = URL(fileURLWithPath: CommandLine.arguments[2])
try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
guard let document = PDFDocument(url: input) else { fatalError("Cannot open report") }
for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { continue }
    let image = page.thumbnail(of: NSSize(width: 1000, height: 1415), for: .mediaBox)
    guard let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
          let png = bitmap.representation(using: .png, properties: [:]) else { fatalError("Cannot render page") }
    try png.write(to: destination.appendingPathComponent(String(format: "page_%02d.png", index + 1)))
}
print("Rendered \(document.pageCount) preview pages")
