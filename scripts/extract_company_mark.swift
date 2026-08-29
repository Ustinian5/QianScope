import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

guard CommandLine.arguments.count == 5 else {
    fputs("usage: extract_company_mark INPUT WHITE_OUTPUT INK_OUTPUT ICON_OUTPUT\n", stderr)
    exit(2)
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let whiteURL = URL(fileURLWithPath: CommandLine.arguments[2])
let inkURL = URL(fileURLWithPath: CommandLine.arguments[3])
let iconURL = URL(fileURLWithPath: CommandLine.arguments[4])

guard
    let source = CGImageSourceCreateWithURL(inputURL as CFURL, nil),
    let sourceImage = CGImageSourceCreateImageAtIndex(source, 0, nil)
else {
    fputs("unable to read input image\n", stderr)
    exit(3)
}

let width = sourceImage.width
let height = sourceImage.height
let colorSpace = CGColorSpaceCreateDeviceRGB()
let bitmapInfo = CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue
var sourcePixels = [UInt8](repeating: 0, count: width * height * 4)

guard let sourceContext = CGContext(
    data: &sourcePixels,
    width: width,
    height: height,
    bitsPerComponent: 8,
    bytesPerRow: width * 4,
    space: colorSpace,
    bitmapInfo: bitmapInfo
) else {
    fputs("unable to create source bitmap context\n", stderr)
    exit(4)
}

sourceContext.draw(sourceImage, in: CGRect(x: 0, y: 0, width: width, height: height))

func luminance(at pixelIndex: Int) -> Int {
    let base = pixelIndex * 4
    return (54 * Int(sourcePixels[base]) + 183 * Int(sourcePixels[base + 1]) + 19 * Int(sourcePixels[base + 2])) >> 8
}

// Find horizontal content bands without assuming whether the bitmap rows are top-down or bottom-up.
// The orbital mark is the tallest band; the Chinese and English wordmarks are shorter bands below it.
var activeRows = [Bool](repeating: false, count: height)
for y in 0..<height {
    var brightPixels = 0
    for x in 0..<width where luminance(at: y * width + x) > 24 {
        brightPixels += 1
        if brightPixels >= 4 { break }
    }
    activeRows[y] = brightPixels >= 4
}

var bands: [ClosedRange<Int>] = []
var bandStart: Int?
var lastActive = -1000
let maximumMergedGap = 18

for y in 0..<height {
    if activeRows[y] {
        if bandStart == nil { bandStart = y }
        lastActive = y
    } else if let start = bandStart, y - lastActive > maximumMergedGap {
        bands.append(start...lastActive)
        bandStart = nil
    }
}
if let start = bandStart { bands.append(start...lastActive) }

guard let markBand = bands.max(by: { $0.count < $1.count }) else {
    fputs("unable to locate the orbital mark\n", stderr)
    exit(5)
}

var minimumX = width - 1
var maximumX = 0
var minimumY = markBand.lowerBound
var maximumY = markBand.upperBound

for y in markBand {
    for x in 0..<width where luminance(at: y * width + x) > 18 {
        minimumX = min(minimumX, x)
        maximumX = max(maximumX, x)
    }
}

let padding = 28
minimumX = max(0, minimumX - padding)
maximumX = min(width - 1, maximumX + padding)
minimumY = max(0, minimumY - padding)
maximumY = min(height - 1, maximumY + padding)

let outputWidth = maximumX - minimumX + 1
let outputHeight = maximumY - minimumY + 1

func makeMarkPixels(red: Int, green: Int, blue: Int) -> [UInt8] {
    var output = [UInt8](repeating: 0, count: outputWidth * outputHeight * 4)
    for outputY in 0..<outputHeight {
        let sourceY = minimumY + outputY
        for outputX in 0..<outputWidth {
            let sourceX = minimumX + outputX
            let lum = luminance(at: sourceY * width + sourceX)
            let alpha = lum <= 16 ? 0 : min(255, (lum - 16) * 255 / 239)
            let outputBase = (outputY * outputWidth + outputX) * 4
            output[outputBase] = UInt8(red * alpha / 255)
            output[outputBase + 1] = UInt8(green * alpha / 255)
            output[outputBase + 2] = UInt8(blue * alpha / 255)
            output[outputBase + 3] = UInt8(alpha)
        }
    }
    return output
}

func image(from pixels: [UInt8], width: Int, height: Int) -> CGImage? {
    let data = Data(pixels) as CFData
    guard let provider = CGDataProvider(data: data) else { return nil }
    return CGImage(
        width: width,
        height: height,
        bitsPerComponent: 8,
        bitsPerPixel: 32,
        bytesPerRow: width * 4,
        space: colorSpace,
        bitmapInfo: CGBitmapInfo(rawValue: bitmapInfo),
        provider: provider,
        decode: nil,
        shouldInterpolate: true,
        intent: .defaultIntent
    )
}

func writePNG(_ image: CGImage, to url: URL) {
    guard let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        fputs("unable to create PNG destination\n", stderr)
        exit(6)
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        fputs("unable to write PNG\n", stderr)
        exit(7)
    }
}

let whitePixels = makeMarkPixels(red: 255, green: 255, blue: 255)
let inkPixels = makeMarkPixels(red: 29, green: 32, blue: 37)
guard
    let whiteImage = image(from: whitePixels, width: outputWidth, height: outputHeight),
    let inkImage = image(from: inkPixels, width: outputWidth, height: outputHeight)
else {
    fputs("unable to create extracted mark images\n", stderr)
    exit(8)
}

writePNG(whiteImage, to: whiteURL)
writePNG(inkImage, to: inkURL)

let iconSize = 512
var iconPixels = [UInt8](repeating: 0, count: iconSize * iconSize * 4)
guard let iconContext = CGContext(
    data: &iconPixels,
    width: iconSize,
    height: iconSize,
    bitsPerComponent: 8,
    bytesPerRow: iconSize * 4,
    space: colorSpace,
    bitmapInfo: bitmapInfo
) else {
    fputs("unable to create icon context\n", stderr)
    exit(9)
}

iconContext.setFillColor(CGColor(red: 0, green: 0, blue: 0, alpha: 1))
iconContext.fill(CGRect(x: 0, y: 0, width: iconSize, height: iconSize))
iconContext.interpolationQuality = .high
let availableWidth: CGFloat = 430
let availableHeight: CGFloat = 300
let scale = min(availableWidth / CGFloat(outputWidth), availableHeight / CGFloat(outputHeight))
let drawWidth = CGFloat(outputWidth) * scale
let drawHeight = CGFloat(outputHeight) * scale
let drawRect = CGRect(
    x: (CGFloat(iconSize) - drawWidth) / 2,
    y: (CGFloat(iconSize) - drawHeight) / 2,
    width: drawWidth,
    height: drawHeight
)
iconContext.draw(whiteImage, in: drawRect)
guard let iconImage = iconContext.makeImage() else {
    fputs("unable to create app icon\n", stderr)
    exit(10)
}
writePNG(iconImage, to: iconURL)

print("extracted mark: \(outputWidth)x\(outputHeight)")
