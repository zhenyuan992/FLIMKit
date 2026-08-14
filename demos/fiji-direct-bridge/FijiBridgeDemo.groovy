#@ String baseUrl
#@ String token

import ij.io.Opener
import java.io.ByteArrayInputStream
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.util.Locale


def client = HttpClient.newHttpClient()

def fetchTiff = { String imageId, String title ->
    def request = HttpRequest.newBuilder()
        .uri(URI.create("${baseUrl}/v1/images/${imageId}.tif"))
        .header('Authorization', "Bearer ${token}")
        .GET()
        .build()
    def response = client.send(request, HttpResponse.BodyHandlers.ofByteArray())
    if (response.statusCode() != 200) {
        throw new IllegalStateException("GET ${imageId} returned ${response.statusCode()}")
    }
    def image = new Opener().openTiff(
        new ByteArrayInputStream(response.body()), title)
    if (image == null) {
        throw new IllegalStateException("Fiji could not decode ${imageId} TIFF")
    }
    if (image.width != 7 || image.height != 5) {
        throw new IllegalStateException(
            "${imageId} shape was ${image.width}x${image.height}, expected 7x5")
    }
    return image
}

def intensity = fetchTiff('intensity', 'FLIMKit intensity')
def lifetime = fetchTiff('lifetime', 'FLIMKit lifetime')
def intensityValue = intensity.getProcessor().getf(6, 4)
def lifetimeValue = lifetime.getProcessor().getf(6, 4)
if (intensityValue != 34.0f || Math.abs(lifetimeValue - 3.4f) > 1e-6f) {
    throw new IllegalStateException(
        "pixel mismatch: intensity=${intensityValue}, lifetime=${lifetimeValue}")
}
println(String.format(
    Locale.US,
    'FIJI_IMAGES_OK intensity=%.1f lifetime=%.1f',
    intensityValue,
    lifetimeValue,
))

def geojson = '''{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {"name": "Fiji polygon"},
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[1.25, 2.5], [4.5, 2.5], [3.0, 4.0], [1.25, 2.5]]]
    }
  }]
}'''

def postRequest = HttpRequest.newBuilder()
    .uri(URI.create("${baseUrl}/v1/rois"))
    .header('Authorization', "Bearer ${token}")
    .header('Content-Type', 'application/geo+json')
    .POST(HttpRequest.BodyPublishers.ofString(geojson, StandardCharsets.UTF_8))
    .build()
def postResponse = client.send(
    postRequest, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8))
if (postResponse.statusCode() != 200) {
    throw new IllegalStateException(
        "POST ROIs returned ${postResponse.statusCode()}: ${postResponse.body()}")
}
if (!postResponse.body().contains('"received_features": 1')) {
    throw new IllegalStateException("unexpected POST response: ${postResponse.body()}")
}
println('FIJI_ROI_POST_OK features=1')
System.exit(0)
