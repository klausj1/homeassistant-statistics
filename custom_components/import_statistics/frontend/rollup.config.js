import resolve from '@rollup/plugin-node-resolve';
import typescript from '@rollup/plugin-typescript';

export default {
    input: 'src/index.ts',
    output: {
        file: 'dist/index.js',
        format: 'iife',
        name: 'ImportStatisticsPanel',
        sourcemap: true,
    },
    plugins: [
        resolve(),
        typescript({
            tsconfig: './tsconfig.json',
        }),
    ],
};
