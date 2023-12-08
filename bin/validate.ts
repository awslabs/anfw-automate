import * as fs from 'fs';
import Ajv from 'ajv';

const schemaPath = './schema.json'; // Path to your JSON schema file
const dataPath = './config.json'; // Path to your JSON data file

const ajv = new Ajv();
const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

const validate = ajv.compile(schema);

if (validate(data)) {
    console.log('JSON data is valid.');
} else {
    console.error('JSON data is invalid.');
    console.error(validate.errors);
}
