import React from 'react';
import { render, screen } from '@testing-library/react';
import { DataDictionariesSection } from '../../../components/resource/DataDictionariesSection';

describe('DataDictionariesSection', () => {
  it('renders dictionaries and nested child rows', () => {
    render(
      <DataDictionariesSection
        dictionaries={[
          {
            id: 1,
            friendlier_id: 'resource-1',
            name: 'Road Attributes',
            description: 'Definitions for road fields',
            staff_notes: null,
            tags: '',
            position: 1,
            created_at: null,
            updated_at: null,
            entries: [
              {
                id: 101,
                resource_data_dictionary_id: 1,
                friendlier_id: 'resource-1',
                field_name: 'road_class',
                field_type: 'string',
                values: 'Interstate, State, County',
                definition: 'Road classification',
                definition_source: 'DOT',
                parent_field_name: null,
                position: 1,
                created_at: null,
                updated_at: null,
              },
              {
                id: 102,
                resource_data_dictionary_id: 1,
                friendlier_id: 'resource-1',
                field_name: 'road_class_code',
                field_type: 'integer',
                values: '1-5',
                definition: 'Encoded class value',
                definition_source: 'DOT',
                parent_field_name: 'road_class',
                position: 2,
                created_at: null,
                updated_at: null,
              },
            ],
          },
        ]}
      />
    );

    expect(screen.getByText('Data Dictionary')).toBeInTheDocument();
    expect(screen.getByText('Road Attributes')).toBeInTheDocument();
    expect(screen.getByText('road_class')).toBeInTheDocument();
    expect(screen.getByText('road_class_code')).toBeInTheDocument();
    expect(screen.getByText('Field Name')).toBeInTheDocument();
    expect(screen.getByText('Definition Source')).toBeInTheDocument();
  });
});
