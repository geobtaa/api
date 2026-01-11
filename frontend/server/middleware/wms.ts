import type { IncomingMessage, ServerResponse } from 'http';

interface WmsParams {
  URL: string;
  LAYERS: string;
  BBOX: string;
  WIDTH: string;
  HEIGHT: string;
  QUERY_LAYERS: string;
  X: string;
  Y: string;
  SERVICE?: string;
  VERSION?: string;
  REQUEST?: string;
  STYLES?: string;
  SRS?: string;
  EXCEPTIONS?: string;
  INFO_FORMAT?: string;
  [key: string]: string | undefined;
}

export async function handleWmsRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  // Log the POST body
  const body = (req as any).body; // body is already parsed by express.json()
  console.log('POST Body:', body);

  // Fetch the URL value from WmsParams
  const wmsUrl = body.URL;
  console.log('WMS URL:', wmsUrl);
  
  // Create a copy of the body without the URL and merge additional WMS parameters
  const { URL, ...bodyWithoutUrl } = body;
  const additionalParams = {
    SERVICE: 'WMS',
    VERSION: '1.1.1',
    REQUEST: 'GetFeatureInfo',
    STYLES: '',
    SRS: 'EPSG:4326',
    EXCEPTIONS: 'application/json',
    INFO_FORMAT: 'application/json'
  };
  const mergedParams = { ...bodyWithoutUrl, ...additionalParams };
  console.log('Merged Params:', mergedParams);

  try {
    // Construct the query string from mergedParams
    const queryString = new URLSearchParams(mergedParams as Record<string, string>).toString();
    console.log('Query String:', queryString);

    const response = await fetch(`${wmsUrl}?${queryString}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });

    const responseBodyText = await response.text();
    console.log('WMS Response Body:', responseBodyText);

    if (!response.ok) {
      console.error('WMS Response Error:', {
        status: response.status,
        statusText: response.statusText,
        body: responseBodyText
      });
      throw new Error(`WMS request failed: ${response.status} ${response.statusText}\n${responseBodyText}`);
    }

    const data = JSON.parse(responseBodyText);
    console.log('WMS Response:', data);

    // Send HTTP 200 response with the data
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(data));
  } catch (error) {
    console.error('WMS Request Error:', error);
    res.statusCode = 500;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ error: 'Internal Server Error' }));
  }
} 
